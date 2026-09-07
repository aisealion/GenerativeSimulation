from engine.norms.base import Norm, NormDecision


class Round20Norm(Norm):
    """Round 20 norm implementation.

    * Per‑trip: a fisher may take up to **30 % of the lake’s current stock** per trip,
      **capped at 4 kg**. If the raw catch exceeds this bound the excess is returned
      and the fisher receives a sanction.
    * Monthly cumulative: a fisher may not cumulatively take more than **60 % of the
      lake’s stock at the start of the month**. Excess is returned and a sanction is
      issued.
    """

    type_name = "round_20"

    def _init_month_state(self, context):
        """Initialize or retrieve persistent month‑level state.

        Stored in ``norm_state`` because it must survive across rounds.
        Keeps the starting stock for the month and a per‑agent cumulative tally.
        """
        state = context.norm_state(self.key)
        if "month_start_stock" not in state:
            state["month_start_stock"] = context.stock_before
            state["cumulative"] = {}
        return state

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        note_parts = []
        sanction = None

        # --- per‑trip cap -------------------------------------------------
        trip_cap = min(0.30 * context.stock_before, 4.0)
        kept_kg = raw_kg
        if raw_kg > trip_cap:
            kept_kg = trip_cap
            sanction = "trip_limit_exceeded"
            note_parts.append(
                f"trip cap exceeded ({raw_kg:.2f} kg) – limited to {trip_cap:.2f} kg"
            )

        # --- monthly cumulative cap --------------------------------------
        month_state = self._init_month_state(context)
        cumulative = month_state["cumulative"]
        prior_total = cumulative.get(agent_id, 0.0)
        prospective_total = prior_total + kept_kg
        month_cap = 0.60 * month_state["month_start_stock"]
        if prospective_total > month_cap:
            allowed = max(month_cap - prior_total, 0.0)
            excess = kept_kg - allowed
            kept_kg = allowed
            sanction = "monthly_cumulative_exceeded" if sanction is None else sanction
            note_parts.append(
                f"monthly cumulative cap exceeded (cap {month_cap:.2f} kg), {excess:.2f} kg returned"
            )
        # store the updated cumulative total (the amount actually kept)
        cumulative[agent_id] = prior_total + kept_kg

        note = ", ".join(note_parts) if note_parts else None
        if sanction:
            return NormDecision.violation(kept_kg=kept_kg, sanction=sanction, note=note)
        else:
            return NormDecision.adjust(kept_kg=kept_kg, note=note)

    def on_round_end(self, context, round_results):
        # No special end‑of‑round logic for this norm.
        return None
