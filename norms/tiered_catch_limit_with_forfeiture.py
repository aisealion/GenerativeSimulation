# Tiered catch limit norm with forfeiture: enforces different limits based on reserve levels.
# High reserves (>= threshold) get a higher limit (25% or 30kg).
# Low reserves (< threshold) get a lower limit (12% or 15kg).
# Violations result in immediate forfeiture of excess (returned to lake) and a one-trip ban.

from engine.norms.base import Norm, NormDecision


class TieredCatchLimitWithForfeitureNorm(Norm):
    """
    Enforces a tiered dual catch limit based on reserve levels:
    - High reserves (>= threshold): percent of stock OR fixed kg amount, whichever is smaller
    - Low reserves (< threshold): lower percent of stock OR lower fixed kg amount

    Violations result in:
    1. Immediate forfeiture of excess catch (returned to lake stock)
    2. A ban for the following trip
    """

    type_name = "tiered_catch_limit_with_forfeiture"

    def is_eligible(self, context, agent_id):
        """
        Check if agent is eligible to fish.
        Returns False if agent is banned for this round.
        """
        state = context.norm_state(self.key)
        current_round = context.round_number

        # Check if banned
        bans = state.get("ban_until", {})
        ban_until = bans.get(agent_id, 0)
        if current_round < ban_until:
            return False

        return True

    def describe(self, context, agent_id):
        """
        Return a description of current constraints for this agent.
        """
        state = context.norm_state(self.key)
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
        high_reserve_threshold = self.params.get("high_reserve_threshold", 20.0)
        high_reserve_percent = self.params.get("high_reserve_percent", 0.25)
        high_reserve_kg_cap = self.params.get("high_reserve_kg_cap", 30.0)
        low_reserve_percent = self.params.get("low_reserve_percent", 0.12)
        low_reserve_kg_cap = self.params.get("low_reserve_kg_cap", 15.0)

        # Get agent's reserves
        payoff = context.runtime.get("payoff", {}).get(agent_id, 0.0)

        # Determine tier and calculate limit
        if payoff >= high_reserve_threshold:
            tier = "high"
            limit_percent = context.stock_before * high_reserve_percent
            effective_limit = min(limit_percent, high_reserve_kg_cap)
            descriptions.append(
                f"Your reserves are {payoff:.1f}kg (high tier). "
                f"Your catch limit is the lesser of {high_reserve_percent*100:.0f}% of stock "
                f"({limit_percent:.1f}kg) or {high_reserve_kg_cap:.0f}kg — effective limit: {effective_limit:.1f}kg."
            )
        else:
            tier = "low"
            limit_percent = context.stock_before * low_reserve_percent
            effective_limit = min(limit_percent, low_reserve_kg_cap)
            descriptions.append(
                f"Your reserves are {payoff:.1f}kg (low tier, below {high_reserve_threshold:.0f}kg). "
                f"Your catch limit is the lesser of {low_reserve_percent*100:.0f}% of stock "
                f"({limit_percent:.1f}kg) or {low_reserve_kg_cap:.0f}kg — effective limit: {effective_limit:.1f}kg."
            )

        # Show lake stock
        descriptions.append(f"Lake stock: {context.stock_before:.1f}kg.")

        # Check if has violation history
        violations = state.get("violations", {})
        if agent_id in violations:
            violation_round = violations[agent_id]
            descriptions.append(f"Note: You had a violation in round {violation_round}.")

        return " ".join(descriptions)

    def on_round_start(self, context):
        """
        Initialize round-specific tracking.
        """
        scratch = context.round_scratch(self.key)
        scratch["excess_this_round"] = {}
        scratch["tier_this_round"] = {}

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """
        Apply the tiered catch limit logic with forfeiture.

        Process:
        1. Determine tier based on reserves
        2. Calculate allowed amount based on tier
        3. Check current catch against limit
        4. Forfeit excess immediately if violated
        5. Record violation and trigger ban
        """
        # Get parameters
        high_reserve_threshold = self.params.get("high_reserve_threshold", 20.0)
        high_reserve_percent = self.params.get("high_reserve_percent", 0.25)
        high_reserve_kg_cap = self.params.get("high_reserve_kg_cap", 30.0)
        low_reserve_percent = self.params.get("low_reserve_percent", 0.12)
        low_reserve_kg_cap = self.params.get("low_reserve_kg_cap", 15.0)
        ban_rounds = self.params.get("ban_rounds", 1)
        current_round = context.round_number

        state = context.norm_state(self.key)
        if "violations" not in state:
            state["violations"] = {}
        if "ban_until" not in state:
            state["ban_until"] = {}

        scratch = context.round_scratch(self.key)
        if "excess_this_round" not in scratch:
            scratch["excess_this_round"] = {}
        if "tier_this_round" not in scratch:
            scratch["tier_this_round"] = {}

        # Step 1: Determine tier based on reserves
        payoff = context.runtime.get("payoff", {}).get(agent_id, 0.0)

        if payoff >= high_reserve_threshold:
            tier = "high"
            percent_limit = high_reserve_percent
            kg_cap = high_reserve_kg_cap
        else:
            tier = "low"
            percent_limit = low_reserve_percent
            kg_cap = low_reserve_kg_cap

        # Record tier for this round
        scratch["tier_this_round"][agent_id] = tier

        # Step 2: Calculate allowed amount based on tier
        limit_percent = context.stock_before * percent_limit
        effective_limit = min(limit_percent, kg_cap)

        # Step 3: Check current catch against limit
        if raw_kg > effective_limit:
            # Violation: excess must be returned immediately
            excess = raw_kg - effective_limit
            kept_kg = effective_limit

            # Record violation and ban
            state["violations"][agent_id] = current_round
            ban_until = current_round + ban_rounds + 1  # Can fish again starting at this round
            state["ban_until"][agent_id] = ban_until

            # Record excess to be returned to stock
            scratch["excess_this_round"][agent_id] = excess

            # Build violation note
            tier_description = "high" if tier == "high" else "low"
            violation_note = (
                f"Your catch of {raw_kg:.1f}kg exceeded your {tier_description} tier limit of {effective_limit:.1f}kg "
                f"(reserves: {payoff:.1f}kg). The excess {excess:.1f}kg has been returned to the lake. "
                f"You are banned from fishing in round {current_round + 1}."
            )

            return NormDecision.violation(
                kept_kg=kept_kg,
                sanction="catch_limit_exceeded",
                note=violation_note
            )

        # No violation
        return NormDecision.allow(raw_kg)

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """
        No additional per-agent processing needed after settlement.
        """
        pass

    def on_round_end(self, context, round_results):
        """
        Return all excess catch to lake stock.
        """
        scratch = context.round_scratch(self.key)
        excess_this_round = scratch.get("excess_this_round", {})

        # Sum all excess amounts
        total_excess = sum(excess_this_round.values())

        if total_excess > 0:
            # Get current stock after regrowth
            current_stock = context.stock_override_kg
            if current_stock is None:
                # Fallback: calculate from physics if not set
                from engine.physics import apply_regrowth
                total_harvested = sum(
                    r["harvested_kg"] for r in round_results.values()
                )
                stock_after_harvest = context.stock_before - total_harvested
                current_stock = apply_regrowth(stock_after_harvest)

            # Add excess back to stock
            new_stock = current_stock + total_excess
            context.override_stock_after_regrowth(new_stock)
