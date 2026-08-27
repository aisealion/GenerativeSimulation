# catch_limit — a per-trip kg ceiling, flat or as a percentage of current
# stock. Absorbs mechanisms/effort.py's former effort_cap() wholesale (same
# per-agent-override behavior), generalized to also support a
# percentage-of-stock limit that recomputes every round.
#
# Config (one entry of state["config"]["norms"]):
#     {
#       "type": "catch_limit",
#       "id": "catch_limit",                   # optional, defaults to "type"
#       "limit_kg": 12,                        # flat per-trip ceiling, OR
#       "limit_pct_of_stock": 0.1,             # fraction of stock_before, OR
#       "limits_by_agent_kg": {"agent_3": 8}   # optional per-agent override,
#                                               # takes precedence over either
#     }
# If both limit_kg and limit_pct_of_stock are set, limit_pct_of_stock wins
# (it's always current; limit_kg is not).

from engine.norms.base import Norm, NormDecision


class CatchLimitNorm(Norm):
    type_name = "catch_limit"

    def _limit_for(self, context, agent_id):
        # Updated policy:
        # - Fishing only allowed if lake biomass ≥12 kg.
        # - Each fisher may take up to 2 kg per trip.
        #   * 1 kg is guaranteed subsistence.
        #   * The second kilogram is optional and limited by 5 % of the current stock.
        stock = context.stock_before
        if stock < 12:
            return 0.0
        # Optional portion cannot exceed 5 % of stock, capped at 1 kg
        optional_limit = min(1.0, 0.05 * stock)
        return 1.0 + optional_limit

    def describe(self, context, agent_id):
        limit = self._limit_for(context, agent_id)
        if limit == 0.0:
            return None
        return f"You currently have an agreed limit of {limit:g}kg for this trip."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        limit = self._limit_for(context, agent_id)
        if limit == 0.0:
            # Suspension: fisher keeps nothing but no violation flag
            return NormDecision.allow(0.0)
        if proposed_kg <= limit:
            return NormDecision.allow(proposed_kg)
        return NormDecision.violation(
            kept_kg=limit,
            sanction="over_cap",
            note=f"That's more than your {limit:g}kg limit for the trip — the rest wasn't counted.",
        )
