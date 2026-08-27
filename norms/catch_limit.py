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
        # New policy: max 1.2 kg or 12 % of current lake biomass, whichever is lower.
        stock = context.stock_before
        limit_by_percent = 0.12 * stock
        return min(1.2, limit_by_percent)

    def describe(self, context, agent_id):
        limit = self._limit_for(context, agent_id)
        if limit is None:
            return None
        return f"You currently have an agreed limit of {limit:.0f}kg for this trip."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        limit = self._limit_for(context, agent_id)
        if limit is None or proposed_kg <= limit:
            return NormDecision.allow(proposed_kg)
        return NormDecision.violation(
            kept_kg=limit,
            sanction="over_cap",
            note=f"That's more than your {limit:.0f}kg limit for the trip — the rest wasn't counted.",
        )
