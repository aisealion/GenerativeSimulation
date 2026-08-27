# sustenance_cap — a per-trip catch limit set as a percentage of current stock,
# with a guaranteed minimum sustenance amount and a graduated penalty for
# violations: excess over the cap is partially released (50%) rather than
# fully forfeited.
#
# Config:
#     {
#       "type": "sustenance_cap",
#       "id": "sustenance_cap",
#       "limit_pct_of_stock": 0.25,      # fraction of stock_before as cap
#       "min_sustenance_kg": 1.0,        # minimum guaranteed keep regardless of cap
#       "excess_release_fraction": 0.5,  # fraction of excess to release (default 50%)
#       "sanction": "over_cap"           # sanction label for downstream norms
#     }
#
# When proposed_kg exceeds the cap:
#     excess = proposed_kg - cap
#     released = excess * excess_release_fraction
#     kept = proposed_kg - released = cap + excess * (1 - excess_release_fraction)
#
# The min_sustenance_kg acts as a floor: even if the penalty calculation
# would result in less, the fisher keeps at least this amount.

from engine.norms.base import Norm, NormDecision


class SustenanceCapNorm(Norm):
    type_name = "sustenance_cap"

    def _cap(self, context):
        pct = self.params.get("limit_pct_of_stock", 0.25)
        return pct * context.stock_before

    def _min_sustenance(self):
        return self.params.get("min_sustenance_kg", 1.0)

    def _release_fraction(self):
        return self.params.get("excess_release_fraction", 0.5)

    def describe(self, context, agent_id):
        cap = self._cap(context)
        min_keep = self._min_sustenance()
        return f"You may keep up to {cap:.0f}kg this trip, with at least {min_keep:.0f}kg reserved for sustenance. Excess catch will be partially released."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        cap = self._cap(context)
        min_keep = self._min_sustenance()
        release_frac = self._release_fraction()
        sanction_label = self.params.get("sanction", "over_cap")

        # Ensure at least the sustenance minimum
        if proposed_kg <= cap:
            # Within cap - allow but ensure minimum sustenance
            kept = max(proposed_kg, min_keep) if proposed_kg < min_keep else proposed_kg
            if kept > proposed_kg:
                return NormDecision.adjust(
                    kept_kg=kept,
                    note=f"Your catch was topped up to the {min_keep:.0f}kg sustenance minimum."
                )
            return NormDecision.allow(kept)

        # Exceeds cap - apply partial release penalty
        excess = proposed_kg - cap
        released = excess * release_frac
        kept = proposed_kg - released

        # Ensure floor
        kept = max(kept, min_keep)

        return NormDecision.violation(
            kept_kg=kept,
            sanction=sanction_label,
            note=f"You exceeded the {cap:.0f}kg cap. You released {released:.0f}kg (50% of the excess) and kept {kept:.0f}kg."
        )
