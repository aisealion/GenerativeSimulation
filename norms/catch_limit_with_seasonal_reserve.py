# Catch limit norm with seasonal reserve: enforces 6kg per-trip limit,
# collective 90% stock rule, 10% reserve deposit, and 12% season-end target.
#
# Key features:
# - Fixed 6kg per-trip individual cap
# - Collective cap: sum of all catches cannot exceed 90% of round-start stock
# - 10% of every kept catch deposited into shared reserve
# - At season end, reserve must be >= 12% of final stock
# - If shortfall, redistribute proportionally based on season catches
# - Ban for limit violations or unpaid obligations

from engine.norms.base import Norm, NormDecision


class CatchLimitWithSeasonalReserveNorm(Norm):
    """
    Enforces:
    1. Fixed 6kg per-trip individual limit (excess forfeited to reserve)
    2. Collective 90% rule (cumulative harvest cannot exceed 90% of stock)
    3. 10% deposit from every kept catch into shared reserve
    4. Season-end check: reserve must be >= 12% of final stock
    5. Proportional shortfall redistribution if reserve target not met
    6. One-trip ban for violations or unpaid obligations
    """

    type_name = "catch_limit_with_seasonal_reserve"

    def is_eligible(self, context, agent_id):
        """
        Check if agent is eligible to fish.
        Returns False if:
        - Agent is banned for this round
        - Collective 90% cap has been reached
        """
        state = context.norm_state(self.key)
        current_round = context.round_number

        # Check if banned
        bans = state.get("ban_until", {})
        ban_until = bans.get(agent_id, 0)
        if current_round < ban_until:
            return False

        # Check collective cap
        scratch = context.round_scratch(self.key)
        cumulative = scratch.get("round_cumulative_harvest", 0)
        max_allowed = scratch.get("max_allowed_this_round", float('inf'))
        if cumulative >= max_allowed:
            return False

        return True

    def describe(self, context, agent_id):
        """
        Return a description of current constraints for this agent.
        """
        state = context.norm_state(self.key)
        scratch = context.round_scratch(self.key)
        current_round = context.round_number

        descriptions = []

        # Check if banned
        bans = state.get("ban_until", {})
        ban_until = bans.get(agent_id, 0)
        if current_round < ban_until:
            rounds_remaining = ban_until - current_round
            descriptions.append(f"You are banned from fishing for {rounds_remaining} more round(s).")
            return " ".join(descriptions)

        # Get parameters
        max_kg = self.params.get("max_kg_per_trip", 6.0)
        reserve_pct = self.params.get("reserve_deposit_percent", 0.10)

        # Show collective availability
        cumulative = scratch.get("round_cumulative_harvest", 0)
        max_allowed = scratch.get("max_allowed_this_round", 0)
        remaining_collective = max(0, max_allowed - cumulative)

        if remaining_collective <= 0:
            descriptions.append("The collective harvest limit (90% of stock) has been reached. No more fishing this round.")
            return " ".join(descriptions)

        # Show individual limit
        effective_limit = min(max_kg, remaining_collective)
        descriptions.append(
            f"Your per-trip limit is {max_kg:.1f}kg. "
            f"Collective allowance remaining: {remaining_collective:.1f}kg. "
            f"Your effective limit: {effective_limit:.1f}kg."
        )

        # Show reserve info
        shared_reserve = state.get("shared_reserve", 0.0)
        season_pct = reserve_pct * 100
        descriptions.append(f"Shared reserve: {shared_reserve:.1f}kg ({season_pct:.0f}% of your catch will be deposited).")

        # Check for proportional debt
        debts = state.get("proportional_debts", {})
        if agent_id in debts and debts[agent_id] > 0:
            debt = debts[agent_id]
            descriptions.append(f"You owe {debt:.1f}kg from the season-end reserve shortfall; this will be deducted from your catch.")

        return " ".join(descriptions)

    def on_round_start(self, context):
        """
        Initialize round-specific tracking.
        Called once per round before any agent is processed.
        """
        scratch = context.round_scratch(self.key)
        state = context.norm_state(self.key)

        # Calculate collective cap: 90% of stock at round start
        stock_before = context.stock_before
        min_stock_pct = self.params.get("min_stock_percent_remaining", 0.10)
        max_take_pct = 1.0 - min_stock_pct  # 0.90
        max_allowed = stock_before * max_take_pct

        scratch["max_allowed_this_round"] = max_allowed
        scratch["round_cumulative_harvest"] = 0.0

        # Initialize persistent state if needed
        if "shared_reserve" not in state:
            state["shared_reserve"] = 0.0
        if "season_catches" not in state:
            state["season_catches"] = {}
        if "season_deposits" not in state:
            state["season_deposits"] = {}
        if "ban_until" not in state:
            state["ban_until"] = {}
        if "violations" not in state:
            state["violations"] = {}
        if "proportional_debts" not in state:
            state["proportional_debts"] = {}

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """
        Apply the catch limit logic with seasonal reserve.

        Process:
        1. Check collective availability
        2. Calculate effective individual limit (min of 6kg and remaining collective)
        3. Forfeit excess over limit to reserve
        4. Deduct 10% reserve deposit from kept amount
        5. Deduct any proportional debt from previous season shortfall
        6. Update tracking and return decision
        """
        # Get parameters
        max_kg = self.params.get("max_kg_per_trip", 6.0)
        reserve_pct = self.params.get("reserve_deposit_percent", 0.10)
        ban_rounds = self.params.get("ban_rounds", 1)
        current_round = context.round_number

        state = context.norm_state(self.key)
        scratch = context.round_scratch(self.key)

        cumulative = scratch.get("round_cumulative_harvest", 0)
        max_allowed = scratch.get("max_allowed_this_round", float('inf'))
        remaining_collective = max(0, max_allowed - cumulative)

        # Step 1 & 2: Calculate effective limit
        effective_limit = min(max_kg, remaining_collective)

        # Track violation status
        violation_occurred = False
        violation_reason = None
        forfeited_to_reserve = 0.0

        # Step 3: Apply limit (forfeit excess)
        if raw_kg > effective_limit:
            kept_before_reserve = effective_limit
            forfeited_to_reserve = raw_kg - effective_limit
            violation_occurred = True
            violation_reason = f"exceeded {max_kg:.1f}kg limit" if max_kg < remaining_collective else "exceeded collective 90% cap"
        else:
            kept_before_reserve = raw_kg

        # Step 4: Apply 10% reserve deposit
        deposit = kept_before_reserve * reserve_pct
        final_kept = kept_before_reserve - deposit

        # Update shared reserve
        state["shared_reserve"] += deposit + forfeited_to_reserve

        # Update season tracking
        if agent_id not in state["season_catches"]:
            state["season_catches"][agent_id] = 0.0
        state["season_catches"][agent_id] += kept_before_reserve

        if agent_id not in state["season_deposits"]:
            state["season_deposits"][agent_id] = 0.0
        state["season_deposits"][agent_id] += deposit

        # Step 5: Deduct proportional debt if any
        debts = state.get("proportional_debts", {})
        debt_deduction = 0.0
        if agent_id in debts and debts[agent_id] > 0:
            debt = debts[agent_id]
            debt_deduction = min(debt, final_kept)
            final_kept -= debt_deduction
            state["shared_reserve"] += debt_deduction
            debts[agent_id] -= debt_deduction
            if debts[agent_id] <= 0:
                del debts[agent_id]

        # Step 6: Update cumulative harvest and handle violations
        scratch["round_cumulative_harvest"] = cumulative + kept_before_reserve

        if violation_occurred:
            # Record violation and ban
            state["violations"][agent_id] = current_round
            ban_until = current_round + ban_rounds + 1  # +1 because ban_until is exclusive
            state["ban_until"][agent_id] = ban_until

            note_parts = [
                f"Your catch of {raw_kg:.1f}kg exceeded the limit of {effective_limit:.1f}kg ({violation_reason}).",
                f"The excess {forfeited_to_reserve:.1f}kg has been forfeited to the shared reserve."
            ]

            if deposit > 0:
                note_parts.append(f"A {deposit:.1f}kg deposit ({reserve_pct*100:.0f}%) was contributed to the reserve.")

            if debt_deduction > 0:
                note_parts.append(f"A {debt_deduction:.1f}kg deduction was applied to pay your seasonal debt.")

            note_parts.append(f"You are banned from fishing in round {current_round + 1}.")

            return NormDecision.violation(
                kept_kg=final_kept,
                sanction="catch_limit_exceeded",
                note=" ".join(note_parts)
            )

        # No violation - build normal note
        note_parts = []
        if deposit > 0:
            note_parts.append(f"You contributed {deposit:.1f}kg ({reserve_pct*100:.0f}%) to the shared reserve.")

        if debt_deduction > 0:
            note_parts.append(f"A {debt_deduction:.1f}kg deduction was applied to pay your seasonal debt.")

        if note_parts:
            return NormDecision.adjust(kept_kg=final_kept, note=" ".join(note_parts))

        return NormDecision.allow(final_kept)

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """
        No additional per-agent processing needed after settlement.
        """
        pass

    def on_round_end(self, context, round_results):
        """
        Check season-end reserve target and redistribute shortfall proportionally.

        At season end:
        1. Calculate required reserve (12% of final stock)
        2. If shortfall exists, divide proportionally among fishers
        3. Reset season tracking for next season
        """
        state = context.norm_state(self.key)
        season_end_pct = self.params.get("season_end_reserve_percent", 0.12)

        # Get final stock (after regrowth)
        final_stock = context.stock_override_kg
        if final_stock is None:
            # Fallback: calculate from physics
            from engine.physics import apply_regrowth
            total_harvested = sum(
                r["harvested_kg"] for r in round_results.values()
            )
            stock_after_harvest = context.stock_before - total_harvested
            final_stock = apply_regrowth(stock_after_harvest)

        # Calculate required reserve
        required_reserve = final_stock * season_end_pct
        shared_reserve = state.get("shared_reserve", 0.0)

        # Check for shortfall
        if shared_reserve < required_reserve:
            shortfall = required_reserve - shared_reserve

            # Calculate total season catch
            season_catches = state.get("season_catches", {})
            total_season_catch = sum(season_catches.values())

            if total_season_catch > 0:
                # Distribute shortfall proportionally
                if "proportional_debts" not in state:
                    state["proportional_debts"] = {}

                for agent_id, agent_catch in season_catches.items():
                    if agent_catch > 0:
                        obligation = shortfall * (agent_catch / total_season_catch)
                        if agent_id not in state["proportional_debts"]:
                            state["proportional_debts"][agent_id] = 0.0
                        state["proportional_debts"][agent_id] += obligation

                # The shortfall is conceptually "covered" by the obligations
                # The actual reserve stays at current level, debts will be paid from future catches

        # Reset season tracking
        state["season_catches"] = {}
        state["season_deposits"] = {}
