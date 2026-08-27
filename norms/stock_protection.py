# stock_protection — suspends all fishing when the lake's stock falls below
# a threshold percentage of its original (carrying capacity) level.
#
# Config:
#     {
#       "type": "stock_protection",
#       "id": "stock_protection",
#       "min_stock_pct": 0.40,      # fraction of original stock that must remain
#       "original_stock_kg": 300    # the baseline stock level (carrying capacity)
#     }
#
# When stock_before drops below min_stock_pct * original_stock_kg, no agent
# is eligible to fish that round. Fishing resumes automatically once regrowth
# brings the stock back above the threshold.

from engine.norms.base import Norm, NormDecision


class StockProtectionNorm(Norm):
    type_name = "stock_protection"

    def _threshold_kg(self, context):
        pct = self.params.get("min_stock_pct", 0.40)
        original = self.params.get("original_stock_kg", 300)
        return pct * original

    def _current_stock(self, context):
        return context.stock_before

    def is_eligible(self, context, agent_id):
        threshold = self._threshold_kg(context)
        current = self._current_stock(context)
        return current >= threshold

    def describe(self, context, agent_id):
        threshold = self._threshold_kg(context)
        current = self._current_stock(context)
        if current < threshold:
            return f"Fishing is currently suspended — the lake's stock ({current:.0f}kg) has fallen below the protected threshold ({threshold:.0f}kg)."
        return f"The lake's stock is at {current:.0f}kg, above the protected minimum of {threshold:.0f}kg."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        return NormDecision.allow(proposed_kg)
