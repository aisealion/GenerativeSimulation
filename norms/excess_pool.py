# excess_pool — captures excess catch beyond per‑trip limit and stores it in a communal pool.
# Config:
#   {
#     "type": "excess_pool",
#     "id": "excess_pool",
#     "limit_kg": 18,          # per‑trip catch ceiling (default 18 kg)
#   }
#
# The pool balance lives in the norm's persistent state under "balance_kg".
# No automatic redistribution is performed here – that could be added later in
# on_round_end or via a separate norm.

from engine.norms.base import Norm, NormDecision


class ExcessPoolNorm(Norm):
    type_name = "excess_pool"

    def _pool_state(self, context):
        # Persistent state for the pool balance
        state = context.norm_state(self.key)
        state.setdefault("balance_kg", 0.0)
        return state

    def describe(self, context, agent_id):
        balance = self._pool_state(context)["balance_kg"]
        return f"The communal excess pool currently holds {balance:.0f}kg."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        # Enforce per‑trip limit; excess goes to pool.
        limit = self.params.get("limit_kg", 18)
        if raw_kg <= limit:
            # No excess, keep the proposed amount (which should be raw_kg).
            return NormDecision.allow(proposed_kg)
        excess = raw_kg - limit
        # Add excess to the pool.
        pool = self._pool_state(context)
        pool["balance_kg"] += excess
        # Fisher keeps only the limit.
        return NormDecision.allow(limit)

    def on_round_end(self, context, round_results):
        # No redistribution logic here – placeholder for future extensions.
        return None
