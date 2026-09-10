# Catch limit norm with penalty trips: enforces 5kg per-trip limit,
# collective 85% stock rule, 12% reserve deposit, and 1kg penalty trips for violations.
#
# Key features:
# - Fixed 5kg per-trip individual cap
# - Collective cap: sum of all catches cannot exceed 85% of round-start stock (15% untouched)
# - 12% of every kept catch deposited into shared reserve
# - Penalty trips: 1kg mandatory trips added to ledger for violations
# - Fishers with pending penalties are limited to 1kg per trip until penalties cleared
# - Reserve is locked - no withdrawal mechanism

from engine.norms.base import Norm, NormDecision


class CatchLimitWithPenaltyTripsNorm(Norm):
    """
    Enforces:
    1. Fixed 5kg per-trip individual limit (excess forfeited to reserve)
    2. Collective 85% rule (cumulative harvest cannot exceed 85% of stock; 15% untouched)
    3. 12% deposit from every kept catch into shared reserve
    4. Penalty trips: when fisher violates limits, add 1kg trip to their ledger
    5. Penalty enforcement: fishers with pending penalties limited to 1kg per trip
    6. Reserve is locked - accumulates but cannot be accessed
    """

    type_name = "catch_limit_with_penalty_trips"

    def is_eligible(self, context, agent_id):
        """
        Check if agent is eligible to fish.
        Returns False if:
        - Collective 85% cap has been reached
        (Note: penalty trips don't make you ineligible, they restrict your catch)
        """
        scratch = context.round_scratch(self.key)

        # Check collective cap
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

        descriptions = []

        # Get parameters
        max_kg = self.params.get("max_kg_per_trip", 5.0)
        reserve_pct = self.params.get("reserve_deposit_percent", 0.12)

        # Check collective availability
        cumulative = scratch.get("round_cumulative_harvest", 0)
        max_allowed = scratch.get("max_allowed_this_round", 0)
        remaining_collective = max(0, max_allowed - cumulative)

        if remaining_collective <= 0:
            descriptions.append("The collective harvest limit (85% of stock) has been reached. No more fishing this round.")
            return " ".join(descriptions)

        # Check for pending penalty trips
        penalty_pending = state.get("penalty_trips_pending", {})
        if agent_id in penalty_pending and penalty_pending[agent_id] > 0:
            count = penalty_pending[agent_id]
            descriptions.append(
                f"You have {count} penalty trip(s) pending. "
                f"Your next trip is limited to 1kg (penalty trip). "
                f"You must serve all penalty trips before returning to normal fishing."
            )
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
        descriptions.append(f"Shared reserve: {shared_reserve:.1f}kg ({season_pct:.0f}% of your catch will be deposited). Reserve is currently locked.")

        return " ".join(descriptions)

    def on_round_start(self, context):
        """
        Initialize round-specific tracking.
        Called once per round before any agent is processed.
        """
        scratch = context.round_scratch(self.key)
        state = context.norm_state(self.key)

        # Calculate collective cap: 85% of stock at round start (15% untouched)
        stock_before = context.stock_before
        min_stock_pct = self.params.get("min_stock_percent_remaining", 0.15)
        max_take_pct = 1.0 - min_stock_pct  # 0.85
        max_allowed = stock_before * max_take_pct

        scratch["max_allowed_this_round"] = max_allowed
        scratch["round_cumulative_harvest"] = 0.0

        # Initialize persistent state if needed
        if "shared_reserve" not in state:
            state["shared_reserve"] = 0.0
        if "season_deposits" not in state:
            state["season_deposits"] = {}
        if "penalty_trips_pending" not in state:
            state["penalty_trips_pending"] = {}
        if "penalty_trip_kg_owed" not in state:
            state["penalty_trip_kg_owed"] = {}
        if "violations" not in state:
            state["violations"] = {}

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """
        Apply the catch limit logic with penalty trips.

        Process:
        1. Check for pending penalty trips - if any, serve one (1kg trip)
        2. If no penalties, check collective availability
        3. Calculate effective individual limit (min of 5kg and remaining collective)
        4. Check for violation (exceeds 5kg or would violate 15% stock rule)
        5. If violation: forfeit excess, add 1 penalty trip to ledger
        6. Apply 12% reserve deposit from kept amount
        7. Update tracking and return decision
        """
        # Get parameters
        max_kg = self.params.get("max_kg_per_trip", 5.0)
        reserve_pct = self.params.get("reserve_deposit_percent", 0.12)
        penalty_trip_kg = self.params.get("penalty_trip_kg", 1.0)
        current_round = context.round_number

        state = context.norm_state(self.key)
        scratch = context.round_scratch(self.key)

        cumulative = scratch.get("round_cumulative_harvest", 0)
        max_allowed = scratch.get("max_allowed_this_round", float('inf'))
        remaining_collective = max(0, max_allowed - cumulative)

        # Initialize agent tracking if needed
        if agent_id not in state["season_deposits"]:
            state["season_deposits"][agent_id] = 0.0
        if agent_id not in state["penalty_trips_pending"]:
            state["penalty_trips_pending"][agent_id] = 0
        if agent_id not in state["penalty_trip_kg_owed"]:
            state["penalty_trip_kg_owed"][agent_id] = 0.0

        # Step 1: Check for pending penalty trips
        penalty_pending = state["penalty_trips_pending"][agent_id]
        is_penalty_trip = False

        if penalty_pending > 0:
            # This is a penalty trip - limit to exactly 1kg
            is_penalty_trip = True
            kept_before_reserve = penalty_trip_kg

            # Decrement penalty counters
            state["penalty_trips_pending"][agent_id] -= 1
            state["penalty_trip_kg_owed"][agent_id] -= penalty_trip_kg

            if state["penalty_trips_pending"][agent_id] <= 0:
                state["penalty_trips_pending"][agent_id] = 0
            if state["penalty_trip_kg_owed"][agent_id] <= 0:
                state["penalty_trip_kg_owed"][agent_id] = 0.0

            # For penalty trips, we don't check violations - they're mandatory
            violation_occurred = False
            forfeited_to_reserve = 0.0

        else:
            # Normal fishing trip - apply limits

            # Step 2 & 3: Calculate effective limit
            effective_limit = min(max_kg, remaining_collective)

            # Track violation status
            violation_occurred = False
            violation_reason = None
            forfeited_to_reserve = 0.0

            # Step 4: Check for violation
            if raw_kg > effective_limit:
                kept_before_reserve = effective_limit
                forfeited_to_reserve = raw_kg - effective_limit
                violation_occurred = True

                # Determine violation reason
                if max_kg < remaining_collective:
                    violation_reason = f"exceeded {max_kg:.1f}kg individual limit"
                else:
                    violation_reason = "exceeded collective 85% cap (15% untouched rule)"

                # Step 5: Add penalty trip for violation
                state["penalty_trips_pending"][agent_id] += 1
                state["penalty_trip_kg_owed"][agent_id] += penalty_trip_kg

            else:
                kept_before_reserve = raw_kg

        # Step 6: Apply 12% reserve deposit
        deposit = kept_before_reserve * reserve_pct
        final_kept = kept_before_reserve - deposit

        # Update shared reserve (deposit + any forfeited excess)
        state["shared_reserve"] += deposit + forfeited_to_reserve

        # Update season deposits tracking
        state["season_deposits"][agent_id] += deposit

        # Step 7: Update cumulative harvest
        scratch["round_cumulative_harvest"] = cumulative + kept_before_reserve

        # Build appropriate note based on scenario
        if is_penalty_trip:
            # Penalty trip note
            remaining_penalties = state["penalty_trips_pending"][agent_id]
            note_parts = [
                f"This is a PENALTY TRIP. You were limited to {penalty_trip_kg:.1f}kg.",
                f"You contributed {deposit:.1f}kg ({reserve_pct*100:.0f}%) to the shared reserve."
            ]

            if remaining_penalties > 0:
                note_parts.append(f"You have {remaining_penalties} more penalty trip(s) pending.")
            else:
                note_parts.append("You have served all pending penalty trips. Normal fishing resumes next trip.")

            return NormDecision.adjust(kept_kg=final_kept, note=" ".join(note_parts))

        elif violation_occurred:
            # Violation note
            penalties_now = state["penalty_trips_pending"][agent_id]

            note_parts = [
                f"Your catch of {raw_kg:.1f}kg exceeded the limit of {effective_limit:.1f}kg ({violation_reason}).",
                f"The excess {forfeited_to_reserve:.1f}kg has been forfeited to the shared reserve.",
                f"A penalty trip of {penalty_trip_kg:.1f}kg has been added to your ledger.",
                f"You now have {penalties_now} penalty trip(s) pending.",
                f"You contributed {deposit:.1f}kg ({reserve_pct*100:.0f}%) to the shared reserve from your kept catch."
            ]

            # Record violation
            state["violations"][agent_id] = current_round

            return NormDecision.violation(
                kept_kg=final_kept,
                sanction="catch_limit_exceeded",
                note=" ".join(note_parts)
            )

        else:
            # Normal successful trip
            note_parts = []
            if deposit > 0:
                note_parts.append(f"You contributed {deposit:.1f}kg ({reserve_pct*100:.0f}%) to the shared reserve.")

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
        End of round processing.
        Reserve simply accumulates - no season-end target or redistribution.
        """
        state = context.norm_state(self.key)

        # Reset season deposits tracking for next season
        # (Keep shared_reserve as it accumulates continuously)
        state["season_deposits"] = {}
