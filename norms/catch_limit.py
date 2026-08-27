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
        # Determine the applicable catch limit for this agent.
        # 1. Per‑agent override takes precedence.
        overrides = self.params.get("limits_by_agent_kg", {})
        if isinstance(overrides, dict) and agent_id in overrides:
            return overrides[agent_id]
        # 2. Percentage of current stock, if configured.
        pct = self.params.get("limit_pct_of_stock")
        if pct is not None:
            return pct * context.stock_before
        # 3. Flat kilogram limit, if configured.
        if "limit_kg" in self.params:
            return self.params["limit_kg"]
        # Default per‑trip ceiling per policy: 10% of current stock, capped at 1 kg
        default_limit = min(0.1 * context.stock_before, 1.0)
        return default_limit

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
