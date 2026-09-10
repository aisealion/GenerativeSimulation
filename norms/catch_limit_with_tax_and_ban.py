# Catch limit norm with tax and ban: enforces a cap of X% of stock OR Y kg, whichever is less.
# Unlike forfeiture norms, violations don't reduce the current catch.
# Instead, the fisher pays a tax on their NEXT catch and is banned for one trip.
# Also enforces a minimum reserve requirement to fish.

from engine.norms.base import Norm, NormDecision


class CatchLimitWithTaxAndBanNorm(Norm):
    """
    Enforces a dual catch limit: percent of current stock OR fixed kg amount,
    whichever is smaller. Violations result in:
    1. A tax on the NEXT catch (not the current one)
    2. A ban for the following trip
    3. No forfeiture of the current catch

    Also enforces a minimum reserve requirement — fishers need at least
    min_reserve_kg in their payoff to be eligible to fish.
    """

    type_name = "catch_limit_with_tax_and_ban"

    def is_eligible(self, context, agent_id):
        """
        Check if agent is eligible to fish.
        Returns False if:
        - Reserve is below minimum requirement
        - Agent is banned for this round
        """
        state = context.norm_state(self.key)
        current_round = context.round_number

        # Check minimum reserve requirement
        min_reserve = self.params.get("min_reserve_kg", 1.0)
        payoff = context.runtime.get("payoff", {}).get(agent_id, 0.0)
        if payoff < min_reserve:
            return False

        # Check if banned
        bans = state.get("banned", {})
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
        min_reserve = self.params.get("min_reserve_kg", 1.0)
        payoff = context.runtime.get("payoff", {}).get(agent_id, 0.0)

        descriptions = []

        # Check minimum reserve
        if payoff < min_reserve:
            descriptions.append(f"You need at least {min_reserve:.1f}kg in reserves to fish. You currently have {payoff:.1f}kg.")
            return " ".join(descriptions)

        # Check if banned
        bans = state.get("banned", {})
        ban_until = bans.get(agent_id, 0)
        if current_round < ban_until:
            rounds_remaining = ban_until - current_round
            descriptions.append(f"You are banned from fishing for {rounds_remaining} more round(s).")
            return " ".join(descriptions)

        # Show the limit
        percent_limit = self.params.get("percent_limit", 0.15)
        kg_limit = self.params.get("kg_limit", 20.0)
        tax_kg = self.params.get("tax_kg", 5.0)

        limit_percent = context.stock_before * percent_limit
        effective_limit = min(limit_percent, kg_limit)

        descriptions.append(
            f"The catch limit is the lesser of {percent_limit*100:.0f}% of stock "
            f"({limit_percent:.1f}kg) or {kg_limit:.0f}kg — effective limit: {effective_limit:.1f}kg. "
            f"Exceeding it triggers a {tax_kg:.0f}kg tax on your next catch and a one-trip ban."
        )

        # Show community fund
        community_fund = state.get("community_fund", 0.0)
        descriptions.append(f"Community fund: {community_fund:.1f}kg.")

        # Check if has pending violation (will be taxed this round)
        violations = state.get("violations", {})
        if agent_id in violations:
            violation_round = violations[agent_id]
            if violation_round < current_round:
                descriptions.append(f"You have a pending {tax_kg:.0f}kg tax on this catch from your round {violation_round} violation.")

        return " ".join(descriptions)

    def on_round_start(self, context):
        """
        Initialize round-specific tracking.
        """
        scratch = context.round_scratch(self.key)
        scratch["tax_paid_this_round"] = {}

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """
        Apply the catch limit logic with tax and ban.

        Process:
        1. Check if agent has prior violation → deduct tax from this catch
        2. Check current catch against limit → record violation if exceeded
        3. Violation triggers ban for next round (not this one)
        """
        percent_limit = self.params.get("percent_limit", 0.15)
        kg_limit = self.params.get("kg_limit", 20.0)
        tax_kg = self.params.get("tax_kg", 5.0)
        current_round = context.round_number

        state = context.norm_state(self.key)
        if "violations" not in state:
            state["violations"] = {}
        if "banned" not in state:
            state["banned"] = {}
        if "tax_paid" not in state:
            state["tax_paid"] = {}
        if "community_fund" not in state:
            state["community_fund"] = 0.0

        # Step 1: Apply tax if there's a prior violation
        kept_kg = raw_kg
        tax_note = None
        violations = state["violations"]

        if agent_id in violations:
            violation_round = violations[agent_id]
            # Only apply tax if violation was in a previous round
            if violation_round < current_round:
                # Calculate tax (can't take more than the catch)
                actual_tax = min(tax_kg, raw_kg)
                kept_kg = raw_kg - actual_tax

                # Record tax payment
                if agent_id not in state["tax_paid"]:
                    state["tax_paid"][agent_id] = 0.0
                state["tax_paid"][agent_id] += actual_tax

                # Add to community fund
                state["community_fund"] += actual_tax

                # Clear the violation (tax is now paid)
                del violations[agent_id]

                tax_note = (
                    f"A {actual_tax:.1f}kg tax was deducted from your catch "
                    f"for your round {violation_round} violation. "
                )

        # Step 2: Check current catch against limit
        limit_percent = context.stock_before * percent_limit
        effective_limit = min(limit_percent, kg_limit)

        # Violation if kept_kg exceeds limit
        if kept_kg > effective_limit:
            # Record violation at current round
            violations[agent_id] = current_round

            # Ban for next round (current_round + 1 means banned until round after next)
            # Actually: "loss of permission for the following trip" means next round is banned
            # So ban_until = current_round + 1 (can't fish in round current_round + 1)
            ban_until = current_round + 2  # Can fish again starting at current_round + 2
            state["banned"][agent_id] = ban_until

            # Build note
            violation_note = (
                f"Your catch of {kept_kg:.1f}kg exceeded the limit of {effective_limit:.1f}kg. "
                f"A violation has been recorded. You will pay a {tax_kg:.0f}kg tax on your next catch "
                f"and are banned from fishing in round {current_round + 1}."
            )

            if tax_note:
                violation_note = tax_note + violation_note

            return NormDecision.violation(
                kept_kg=kept_kg,
                sanction="catch_limit_exceeded",
                note=violation_note
            )

        # No violation
        if tax_note:
            return NormDecision.adjust(kept_kg=kept_kg, note=tax_note.strip())

        return NormDecision.allow(kept_kg)

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """
        No additional per-agent processing needed after settlement.
        """
        pass

    def on_round_end(self, context, round_results):
        """
        No stock override needed — no forfeiture in this norm.
        Community fund is already updated during evaluate().
        """
        pass
