from dataclasses import dataclass

from engine.norms.base import Norm, NormDecision


class Round2QuotaNorm(Norm):
    """Implements Round 2 policy.

    * Catch limit: up to 10 % of the lake's current stock per trip, with a
      minimum of 1 kg and a hard cap of 20 kg. Excess is returned to the lake or
      the community reserve.
    * Infractions: exceeding 20 kg or failing to submit a record results in a
      one‑round suspension.
    * If the lake stock falls below 200 kg, the quota for the next round is
      reduced by 5 % (cumulative).
    """

    type_name = "round2_quota"

    # Persistent state keys
    SUSPENDED_UNTIL = "suspended_until"
    REDUCTION_FACTOR = "reduction_factor"

    def is_eligible(self, context, agent_id):
        """Skip agents under suspension."""
        state = context.norm_state(self.key)
        suspended_until = state.get(self.SUSPENDED_UNTIL, 0)
        if context.round_number <= suspended_until:
            return False
        return True

    def on_round_start(self, context):
        """Ensure reduction factor exists (starts at 1.0)."""
        state = context.norm_state(self.key)
        state.setdefault(self.REDUCTION_FACTOR, 1.0)
        return None

    def _compute_quota(self, context):
        """Calculate quota for the current round.

        Base quota = 10 % of current stock, bounded by [1 kg, 20 kg]. Apply any
        cumulative reduction factor, then re‑clamp to the same bounds.
        """
        base = max(0.1 * context.stock_before, 1.0)
        base = min(base, 20.0)
        factor = context.norm_state(self.key).get(self.REDUCTION_FACTOR, 1.0)
        quota = base * factor
        quota = max(min(quota, 20.0), 1.0)
        return quota

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Clamp catch to quota and record infractions.

        * If raw_kg exceeds the quota, keep only the quota amount.
        * If raw_kg exceeds the hard cap of 20 kg, record an infraction and
          suspend the fisher for the next round.
        """
        quota = self._compute_quota(context)
        state = context.norm_state(self.key)
        notes = []
        kept = quota
        if raw_kg > quota:
            excess = raw_kg - quota
            notes.append(f"Exceeded quota by {excess:.1f} kg; kept {quota:.1f} kg.")
        if raw_kg > 20.0:
            # Record infraction and suspend for one round
            state[self.SUSPENDED_UNTIL] = context.round_number + 1
            notes.append("Infraction: exceeded 20 kg cap – suspension applied.")
        note = " ".join(notes) if notes else None
        return NormDecision.adjust(kept, note=note)

    def on_round_end(self, context, round_results):
        """Adjust reduction factor based on post‑regrowth stock.

        If the lake stock after regrowth is below 200 kg, multiply the factor by
        0.95 for the next round; otherwise reset to 1.0.
        """
        state = context.norm_state(self.key)
        final_stock = context.runtime.get("stock_kg")
        if final_stock is not None and final_stock < 200.0:
            factor = state.get(self.REDUCTION_FACTOR, 1.0) * 0.95
            state[self.REDUCTION_FACTOR] = factor
        else:
            state[self.REDUCTION_FACTOR] = 1.0
        return None
