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
        # Determine per‑trip catch limit with precedence:
        #   1. per‑agent override (limits_by_agent_kg)
        #   2. explicit percent of stock (limit_pct_of_stock)
        #   3. explicit flat kg limit (limit_kg)
        # 4. policy fallback: min(1.5 kg, 3% of current stock)
        stock = context.stock_before
        # Suspension condition: if stock is below a minimal viable level (<6 kg), no catch allowed.
        if stock < 6.0:
            return 0.0
        # 1. per‑agent override
        overrides = self.params.get("limits_by_agent_kg", {})
        if isinstance(overrides, dict) and agent_id in overrides:
            return overrides[agent_id]
        # 2. explicit percent of stock
        pct = self.params.get("limit_pct_of_stock")
        if pct is not None:
            return pct * stock
        # 3. explicit flat kg limit
        flat = self.params.get("limit_kg")
        if flat is not None:
            return flat
        # 4. policy fallback
        return min(1.5, 0.03 * stock)

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
        # Determine if limit came from explicit config or policy fallback
        explicit_config = (
            self.params.get("limit_kg") is not None
            or self.params.get("limit_pct_of_stock") is not None
            or self.params.get("limits_by_agent_kg")
        )
        if explicit_config:
            # Exceeds explicit config limit: keep up to limit, excess to reserve
            reserve_state = context.norm_state("reserve")
            excess = raw_kg - limit
            if excess > 0:
                reserve_state["balance_kg"] = reserve_state.get("balance_kg", 0.0) + excess
            # Return the allowed portion with a note indicating a cap was applied.
            return NormDecision.adjust(limit, note=f"{limit:g}kg limit")

        # Policy fallback: any exceed results in full forfeiture to reserve.
        reserve_state = context.norm_state("reserve")
        reserve_state["balance_kg"] = reserve_state.get("balance_kg", 0.0) + raw_kg
        return NormDecision.allow(0.0)
