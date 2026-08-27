# community_cap — round-level constraints on the whole community's catch,
# independent of any individual agent's own cap. Both behaviors are
# independently optional:
#
#     {
#       "type": "community_cap",
#       "id": "community_cap",
#       "cap_kg": 90,                  # OR cap_pct_of_stock — total community
#       "cap_pct_of_stock": 0.3,       # catch ceiling this round, enforced
#                                       # incrementally, first-come-first-served
#                                       # in the same order alive_agent_ids()
#                                       # already iterates in
#       "replenish_if_over_pct": 0.7   # if total community catch this round
#                                       # exceeds this fraction of stock_before,
#                                       # restore the lake to its pre-harvest
#                                       # level instead of the physics-computed
#                                       # post-regrowth figure
#     }
#
# Uses context.round_scratch() for the running per-round tally — a fresh
# HarvestContext every round means this needs no explicit reset.

from engine.norms.base import Norm, NormDecision


class CommunityCapNorm(Norm):
    type_name = "community_cap"

    def _limit(self, context):
        pct = self.params.get("cap_pct_of_stock")
        if pct is not None:
            return pct * context.stock_before
        if "cap_kg" in self.params:
            return self.params.get("cap_kg")
        # No cap configured – treat as unlimited (no-op)
        return None

    def describe(self, context, agent_id):
        limit = self._limit(context)
        if limit is None:
            return None
        used = context.round_scratch(self.key).get("total_kg", 0.0)
        return f"The community has {max(0.0, limit - used):.0f}kg left of its shared allowance for this round."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        limit = self._limit(context)
        if limit is None:
            # No cap – allow all
            return NormDecision.allow(proposed_kg)
        tally = context.round_scratch(self.key)
        used = tally.get("total_kg", 0.0)
        remaining = max(0.0, limit - used)
        if proposed_kg <= remaining:
            tally["total_kg"] = used + proposed_kg
            return NormDecision.allow(proposed_kg)
        # Exceeds remaining allowance
        tally["total_kg"] = used + remaining
        return NormDecision.violation(
            kept_kg=remaining,
            sanction="over_community_cap",
            note="The community's shared allowance for this round was already used up by others, so the rest of your catch wasn't counted.",
        )

    def on_round_end(self, context, round_results):
        threshold = self.params.get("replenish_if_over_pct")
        if threshold is None:
            return
        total_kg = sum(r["harvested_kg"] for r in round_results.values())
        if context.stock_before > 0 and total_kg > threshold * context.stock_before:
            context.override_stock_after_regrowth(context.stock_before)
