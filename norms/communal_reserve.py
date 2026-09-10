"""Communal Reserve Norm: Manages communal reserve with automatic release.

Policy: Surplus over 4kg per trip is deposited into a communal reserve
capped at 70 kg. When lake mass falls below 140 kg, the reserve is
automatically released to raise the lake to 190 kg, distributed
proportionally based on previous round's catch.
"""

from engine.norms.base import Norm, NormDecision


class CommunalReserveNorm(Norm):
    """Manages communal reserve deposits and automatic releases.

    - Tracks reserve balance (capped at 70kg)
    - Handles surplus deposits from catches over 4kg
    - Monitors lake mass and triggers release when below 140kg
    - Calculates proportional distribution based on previous round's catch
    - Releases to lake via stock override
    """

    type_name = "communal_reserve"

    def __init__(self, key, params):
        super().__init__(key, params)
        # Maximum reserve capacity (default: 70kg)
        self.max_reserve_kg = params.get("max_reserve_kg", 70.0)
        # Lake mass threshold to trigger release (default: 140kg)
        self.release_threshold_kg = params.get("release_threshold_kg", 140.0)
        # Target lake mass after release (default: 190kg)
        self.release_target_kg = params.get("release_target_kg", 190.0)
        # Key of the lake_watcher norm to integrate with
        self.watcher_norm_key = params.get("watcher_norm_key", "lake_watcher")
        # Key of the catch_cap norm to check violations
        self.catch_cap_key = params.get("catch_cap_key", "catch_cap")

    def describe(self, context, agent_id):
        """Tell the agent about the communal reserve status."""
        state = context.norm_state(self.key)
        reserve_balance = state.get("reserve_balance_kg", 0.0)

        if reserve_balance >= self.max_reserve_kg:
            return f"The communal reserve is at capacity ({self.max_reserve_kg:.0f}kg). Any surplus catch cannot be deposited."
        else:
            space_remaining = self.max_reserve_kg - reserve_balance
            return f"The communal reserve holds {reserve_balance:.1f}kg (capacity: {self.max_reserve_kg:.0f}kg). Surplus catch over 4kg will be deposited (up to {space_remaining:.1f}kg remaining)."

    def on_round_start(self, context):
        """Check lake mass and trigger reserve release if needed.

        If lake mass is below threshold, calculate required release and
        distribute proportionally based on previous round's catches.
        """
        state = context.norm_state(self.key)
        agents = context.agents

        # Initialize reserve balance if not exists
        if "reserve_balance_kg" not in state:
            state["reserve_balance_kg"] = 0.0

        reserve_balance = state["reserve_balance_kg"]
        current_stock = context.stock_before

        # Check if release is needed (lake below threshold and reserve has fish)
        if current_stock < self.release_threshold_kg and reserve_balance > 0:
            # Calculate required release to reach target
            required_release = self.release_target_kg - current_stock

            # Release only what's needed and available
            actual_release = min(required_release, reserve_balance)

            if actual_release > 0:
                # Get previous round's catches for proportional distribution
                prev_catches = state.get("previous_round_catches", {})
                prev_total = state.get("previous_round_total", 0.0)

                if prev_total > 0 and prev_catches:
                    # Calculate proportional shares
                    distributions = {}
                    for agent_id, catch_kg in prev_catches.items():
                        share_ratio = catch_kg / prev_total
                        distribution_kg = share_ratio * actual_release
                        distributions[agent_id] = {
                            "catch_kg": catch_kg,
                            "share_ratio": share_ratio,
                            "distribution_kg": distribution_kg,
                        }

                    # Record release
                    releases = state.setdefault("releases", [])
                    release_record = {
                        "round": context.round_number,
                        "stock_before_kg": current_stock,
                        "required_kg": required_release,
                        "released_kg": actual_release,
                        "reserve_before_kg": reserve_balance,
                        "reserve_after_kg": reserve_balance - actual_release,
                        "distributions": distributions,
                    }
                    releases.append(release_record)

                    # Update reserve balance
                    state["reserve_balance_kg"] = reserve_balance - actual_release

                    # Record distributions
                    distributions_list = state.setdefault("distributions", [])
                    for agent_id, dist_info in distributions.items():
                        distributions_list.append({
                            "round": context.round_number,
                            "agent_id": agent_id,
                            "agent_name": agents.get(agent_id, {}).get("name", agent_id),
                            "share_ratio": dist_info["share_ratio"],
                            "distribution_kg": dist_info["distribution_kg"],
                        })

                    # Override stock to simulate release into lake
                    new_stock = current_stock + actual_release
                    context.override_stock_after_regrowth(new_stock)

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Handle surplus deposits for catches over 4kg.

        When a fisher catches more than 4kg, the excess is deposited
        into the communal reserve (up to the 70kg cap).
        """
        state = context.norm_state(self.key)
        catch_cap_limit = 4.0  # Matches catch_cap norm

        # Check if this catch exceeds the limit (would have been trimmed by catch_cap)
        if proposed_kg > catch_cap_limit:
            # This shouldn't happen if catch_cap is ordered before this norm
            # But handle it just in case
            surplus = proposed_kg - catch_cap_limit
        else:
            # Check if the original raw catch was over limit
            # If raw was over but proposed is at limit, there's surplus to deposit
            if raw_kg > catch_cap_limit:
                surplus = raw_kg - catch_cap_limit
            else:
                surplus = 0.0

        if surplus > 0:
            # Calculate how much can actually be deposited (respect cap)
            reserve_balance = state.get("reserve_balance_kg", 0.0)
            space_available = self.max_reserve_kg - reserve_balance
            actual_deposit = min(surplus, space_available)

            if actual_deposit > 0:
                # Update reserve balance
                state["reserve_balance_kg"] = reserve_balance + actual_deposit

                # Record deposit
                deposits = state.setdefault("deposits", [])
                deposit_record = {
                    "round": context.round_number,
                    "agent_id": agent_id,
                    "agent_name": context.agents.get(agent_id, {}).get("name", agent_id),
                    "catch_kg": raw_kg,
                    "deposit_kg": actual_deposit,
                    "reserve_before_kg": reserve_balance,
                    "reserve_after_kg": reserve_balance + actual_deposit,
                }
                deposits.append(deposit_record)

                # Record deposit in lake_watcher's ledger
                watcher_state = context.norm_state(self.watcher_norm_key)
                if watcher_state:
                    communal_ledger = watcher_state.setdefault("communal_ledger", [])
                    # Find existing entry for this agent/round or create new one
                    existing_entry = None
                    for entry in communal_ledger:
                        if entry["round"] == context.round_number and entry["agent_id"] == agent_id:
                            existing_entry = entry
                            break

                    if existing_entry:
                        existing_entry["deposit_kg"] = actual_deposit
                        existing_entry["deposit_status"] = True
                    else:
                        communal_ledger.append({
                            "round": context.round_number,
                            "agent_id": agent_id,
                            "agent_name": context.agents.get(agent_id, {}).get("name", agent_id),
                            "catch_kg": proposed_kg,
                            "deposit_kg": actual_deposit,
                            "deposit_status": True,
                            "personal_reserve_kept": True,  # Assumed from mandatory_reserve
                            "violation": False,
                            "recorded_by": "Kai",
                        })

                # Note the deposit
                if actual_deposit < surplus:
                    note = f"Surplus of {surplus:.1f}kg deposited {actual_deposit:.1f}kg to communal reserve (at capacity). {surplus - actual_deposit:.1f}kg returned to lake."
                else:
                    note = f"Surplus of {surplus:.1f}kg deposited into communal reserve (now at {state['reserve_balance_kg']:.1f}kg)."

                return NormDecision.adjust(
                    kept_kg=proposed_kg,
                    note=note
                )

        return NormDecision.allow(proposed_kg)

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Record catch for proportional distribution calculation.

        Store this agent's catch to use for proportional distribution
        in the next round's release.
        """
        state = context.norm_state(self.key)

        # Store catch for next round's proportional calculation
        if "current_round_catches" not in state:
            state["current_round_catches"] = {}

        state["current_round_catches"][agent_id] = harvested_kg

    def on_round_end(self, context, round_results):
        """Prepare catches for next round's proportional distribution.

        Save current round's catches as 'previous_round_catches' for
        use in next round's release calculation.
        """
        state = context.norm_state(self.key)

        # Transfer current catches to previous for next round
        current_catches = state.get("current_round_catches", {})

        if current_catches:
            state["previous_round_catches"] = current_catches.copy()
            state["previous_round_total"] = sum(current_catches.values())
        else:
            # No catches this round - use empty distribution
            state["previous_round_catches"] = {}
            state["previous_round_total"] = 0.0

        # Clear current catches for next round
        state["current_round_catches"] = {}

        # Record round summary
        reserve_balance = state.get("reserve_balance_kg", 0.0)
        round_summaries = state.setdefault("round_summaries", [])
        round_summaries.append({
            "round": context.round_number,
            "reserve_balance_kg": reserve_balance,
            "total_deposits_this_round": sum(
                d["deposit_kg"] for d in state.get("deposits", [])
                if d["round"] == context.round_number
            ),
            "total_released_this_round": sum(
                r["released_kg"] for r in state.get("releases", [])
                if r["round"] == context.round_number
            ),
        })
