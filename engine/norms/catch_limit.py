# catch_limit — enforce per‑trip harvest caps and communal reserve minimum

# Config (example, can be omitted if defaults are OK):
# {
#   "type": "catch_limit",
#   "id": "catch_limit",
#   "max_kg_per_trip": 1.2,
#   "max_percent_of_stock": 0.04,
#   "min_reserve_percent": 0.90,
#   "reserve_violation_note": "Community reserve fell below 90% this round.",
# }

from engine.norms.base import Norm, NormDecision


class CatchLimitNorm(Norm):
    """Enforces the harvest policy from *norm.txt*.

    - Each fisher may keep at most the lower of a fixed kilogram cap and a
      percentage of the lake's current biomass.
    - After all harvests, the lake must retain at least ``min_reserve_percent``
      of its starting biomass. If the community falls short, a note is stored in
      the round's scratch space for downstream observers.
    """

    type_name = "catch_limit"

    # ---------------------------------------------------------------------
    # Helper: compute the per‑trip catch limit for the current stock.
    # ---------------------------------------------------------------------
    def _trip_limit(self, context):
        stock = context.stock_before
        max_kg = self.params.get("max_kg_per_trip", 250.0)
        max_pct = self.params.get("max_percent_of_stock", 0.02) * stock
        return min(max_kg, max_pct)

    # ---------------------------------------------------------------------
    # Norm hooks
    # ---------------------------------------------------------------------
    def describe(self, context, agent_id):
        limit = self._trip_limit(context)
        return f"You may harvest up to {limit:.2f}kg this trip (per‑trip cap)."

    def is_eligible(self, context, agent_id):
        # All agents participate; the 90 % reserve rule is enforced in on_round_end.
        return True

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Apply the per‑trip cap.

        *raw_kg* is the physics‑only catch. *proposed_kg* is what previous norms
        have allowed. We enforce the stricter of the two limits and, if the
        fisher exceeded it, record a violation and a note describing the
        required return/donation.
        """
        limit = self._trip_limit(context)
        if raw_kg <= limit:
            # No cap breach – keep whatever previous norms decided.
            return NormDecision.allow(proposed_kg)

        # Cap breached – keep only up to the limit.
        kept = limit
        excess = raw_kg - limit
        note = (
            f"You exceeded the per‑trip limit of {limit:.2f}kg; "
            f"the extra {excess:.2f}kg must be returned or donated."
        )
        # Use violation to flag the over‑catch – other norms may react to the
        # ``sanction`` string if they care.
        return NormDecision.violation(kept_kg=kept, sanction="overcatch", note=note)

    def on_round_end(self, context, round_results):
        """Check the communal reserve requirement after all agents have
        harvested. If the total kept catch exceeds 10 % of the starting stock,
        store a note in the round‑scratch space so other components (e.g. a UI)
        can surface it.
        """
        total_kept = sum(
            rec.get("harvested_kg", 0.0)
            for rec in round_results.values()
            if rec.get("participated") is not False
        )
        allowed_total = context.stock_before * (1 - self.params.get("min_reserve_percent", 0.90))
        if total_kept > allowed_total:
            # Record the violation note for the whole round.
            note = self.params.get(
                "reserve_violation_note",
                "Community reserve fell below the required 90% after this round.",
            )
            context.round_scratch("reserve_violation")["note"] = note
        # No direct effect on stock – the simulation's physics will handle the
        # actual biomass numbers.
        return None
