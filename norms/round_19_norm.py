from engine.norms.base import Norm, NormDecision


class Round19Norm(Norm):
    """Round 19 norm implementation.

    * Per‑trip: max 2 kg total catch. Must keep at least 1 kg personal.
      If catch > 2 kg, the excess is added to the community pool and the fisher forfeits
      their personal quota for that trip (kept_kg = 0).
    * Monthly community pool: sum of community portions may not exceed the lower of
      30 % of the lake stock at the start of the month or an absolute 3 kg cap.
      Exceeding this triggers a one‑month ban (sanction "monthly_cap_exceeded").
    """

    type_name = "round_19"

    def _init_month_state(self, context):
        """Ensure persistent month‑level state exists.
        Stored in ``norm_state`` because it must survive across rounds.
        """
        state = context.norm_state(self.key)
        if "month_start_stock" not in state:
            # First agent of the month establishes the reference stock.
            state["month_start_stock"] = context.stock_before
            state["monthly_total"] = 0.0
        return state

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        # Per‑trip enforcement.
        note_parts = []
        sanction = None
        # Determine personal keep and community contribution.
        if raw_kg > 2.0:
            # Trip limit exceeded – fisher loses personal keep.
            personal_keep = 0.0
            community = raw_kg  # whole catch goes to community pool.
            sanction = "trip_limit_exceeded"
            note_parts.append(f"trip limit exceeded ({raw_kg:.2f} kg) – personal keep forfeited")
        else:
            # Keep at least 1 kg personal if possible.
            personal_keep = min(raw_kg, 1.0)
            community = max(raw_kg - personal_keep, 0.0)
            if raw_kg > 2.0:
                # This branch is unreachable because of the earlier check but kept for clarity.
                sanction = "trip_limit_exceeded"

        # Monthly cap handling – only applies to the community portion.
        month_state = self._init_month_state(context)
        month_start_stock = month_state["month_start_stock"]
        monthly_total = month_state["monthly_total"]
        prospective_total = monthly_total + community
        month_cap = min(0.30 * month_start_stock, 3.0)
        if prospective_total > month_cap:
            excess = prospective_total - month_cap
            # Reject the excess from the community contribution.
            community_adj = max(community - excess, 0.0)
            month_state["monthly_total"] = monthly_total + community_adj
            note_parts.append(f"monthly cap exceeded (cap {month_cap:.2f} kg), {excess:.2f} kg rejected")
            # Sanction for monthly cap breach.
            sanction = "monthly_cap_exceeded" if sanction is None else sanction
        else:
            month_state["monthly_total"] = prospective_total

        note = ", ".join(note_parts) if note_parts else None
        if sanction:
            return NormDecision.violation(kept_kg=personal_keep, note=note, sanction=sanction)
        else:
            return NormDecision.adjust(kept_kg=personal_keep, note=note)

    def on_round_end(self, context, round_results):
        # No additional end‑of‑round logic needed for this norm.
        return None
