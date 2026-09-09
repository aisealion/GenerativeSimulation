# Catch limit norm: enforces a cap of X% of stock OR Y kg, whichever is less.
# Excess catch is forfeited back to the lake, and violating fishers receive
# a temporary ban.

from engine.norms.base import Norm, NormDecision


class CatchLimitWithForfeitureNorm(Norm):
    """
    Enforces a dual catch limit: percent of current stock OR fixed kg amount,
    whichever is smaller. Violations result in forfeiture of excess catch
    and a one-day fishing ban.
    """

    type_name = "catch_limit_with_forfeiture"

    def is_eligible(self, context, agent_id):
        """
        Check if agent is banned. Returns False if ban_until is in the future.
        """
        state = context.norm_state(self.key)
        bans = state.get("bans", {})
        ban_until = bans.get(agent_id, 0)
        current_round = context.round_number

        # Ban is active if current round is less than ban_until
        # (ban_until is the first round they CAN fish again)
        if current_round < ban_until:
            return False
        return True

    def describe(self, context, agent_id):
        """
        Return a description of current constraints for this agent.
        """
        state = context.norm_state(self.key)
        bans = state.get("bans", {})
        ban_until = bans.get(agent_id, 0)
        current_round = context.round_number

        # If banned, note the ban
        if current_round < ban_until:
            rounds_remaining = ban_until - current_round
            return f"You are banned from fishing for {rounds_remaining} more round(s)."

        # Otherwise, show the limit
        percent_limit = self.params.get("percent_limit", 0.15)
        kg_limit = self.params.get("kg_limit", 20.0)

        limit_percent = context.stock_before * percent_limit
        effective_limit = min(limit_percent, kg_limit)

        return f"The catch limit is the lesser of {percent_limit*100:.0f}% of stock ({limit_percent:.1f}kg) or {kg_limit:.0f}kg — effective limit: {effective_limit:.1f}kg. Excess will be forfeited and you will be banned for one day."

    def on_round_start(self, context):
        """
        Initialize round-specific tracking for forfeitures.
        """
        scratch = context.round_scratch(self.key)
        scratch["forfeited_this_round"] = {}

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """
        Apply the catch limit. If exceeded, forfeit excess and issue ban.
        """
        percent_limit = self.params.get("percent_limit", 0.15)
        kg_limit = self.params.get("kg_limit", 20.0)
        ban_days = self.params.get("ban_days", 1)

        # Calculate the effective limit
        limit_percent = context.stock_before * percent_limit
        effective_limit = min(limit_percent, kg_limit)

        # If within limit, allow full catch
        if raw_kg <= effective_limit:
            return NormDecision.allow(raw_kg)

        # Violation: exceeded the limit
        forfeited = raw_kg - effective_limit
        kept = effective_limit

        # Record forfeiture for this round
        scratch = context.round_scratch(self.key)
        scratch["forfeited_this_round"][agent_id] = forfeited

        # Issue ban
        current_round = context.round_number
        ban_until = current_round + ban_days

        state = context.norm_state(self.key)
        if "bans" not in state:
            state["bans"] = {}
        state["bans"][agent_id] = ban_until

        # Note: forfeited fish go back to the lake (handled in on_round_end)
        note = f"Your catch of {raw_kg:.1f}kg exceeded the limit of {effective_limit:.1f}kg. The excess {forfeited:.1f}kg has been forfeited to the communal pool. You are banned from fishing until round {ban_until}."

        return NormDecision.violation(
            kept_kg=kept,
            sanction="catch_limit_exceeded",
            note=note
        )

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """
        No additional per-agent processing needed after settlement.
        """
        pass

    def on_round_end(self, context, round_results):
        """
        Add all forfeited fish back to the lake stock.
        """
        scratch = context.round_scratch(self.key)
        forfeited_by_agent = scratch.get("forfeited_this_round", {})

        total_forfeited = sum(forfeited_by_agent.values())

        if total_forfeited > 0:
            # Get current stock after regrowth
            current_stock = context.stock_override_kg
            if current_stock is None:
                # Calculate what it would be (stock_before - harvested + regrowth)
                # This is a fallback; normally stock_override_kg should be set
                # by the harvest action before this is called
                from engine.physics import apply_regrowth
                total_harvested = sum(
                    r["harvested_kg"] for r in round_results.values()
                )
                stock_after_harvest = context.stock_before - total_harvested
                current_stock = apply_regrowth(stock_after_harvest)

            # Add forfeited fish back
            new_stock = current_stock + total_forfeited
            context.override_stock_after_regrowth(new_stock)
