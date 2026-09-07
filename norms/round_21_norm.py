from engine.norms.base import Norm, NormDecision


class Round21Norm(Norm):
    """Round 21 norm implementation.

    * Per‑trip: a fisher may take up to **1 kg** per trip.
    * Weekly cumulative: the community’s total harvest may not exceed **70 %** of the lake’s stock at the start of the week,
      and must leave at least **1 kg** in the lake after harvest.
    * Violations (per‑trip or weekly cap exceeded) result in a ban sanction for one week.
    """

    type_name = "round_21"

    def _init_week_state(self, context):
        """Initialize or retrieve per‑week state stored in round_scratch.

        Stores the lake stock at the start of the week and the cumulative
        harvest kept so far this week.
        """
        state = context.round_scratch(self.key)
        if "week_start_stock" not in state:
            state["week_start_stock"] = context.stock_before
            state["cumulative"] = 0.0
        return state

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        note_parts = []
        sanction = None

        # --- per‑trip cap ---------------------------------------------------
        kept_kg = raw_kg
        if raw_kg > 1.0:
            kept_kg = 1.0
            sanction = "ban"
            note_parts.append("trip cap exceeded (>{:.2f} kg) – limited to 1 kg".format(raw_kg))

        # --- weekly cumulative cap ------------------------------------------
        week_state = self._init_week_state(context)
        week_start_stock = week_state["week_start_stock"]
        # enforce both 70 % cap and a minimum 1 kg left in the lake
        cap_seventy = 0.70 * week_start_stock
        cap_min_stock = max(week_start_stock - 1.0, 0.0)
        weekly_cap = min(cap_seventy, cap_min_stock)
        prospective_total = week_state["cumulative"] + kept_kg
        if prospective_total > weekly_cap:
            excess = prospective_total - weekly_cap
            kept_kg = max(kept_kg - excess, 0.0)
            sanction = "ban"
            note_parts.append(
                "weekly cap exceeded (cap {:.2f} kg), reduced by {:.2f} kg".format(
                    weekly_cap, excess
                )
            )

        # update weekly cumulative total with the final kept kilograms
        week_state["cumulative"] = week_state["cumulative"] + kept_kg

        note = ", ".join(note_parts) if note_parts else None
        if sanction:
            return NormDecision.violation(kept_kg=kept_kg, sanction=sanction, note=note)
        else:
            return NormDecision.adjust(kept_kg=kept_kg, note=note)

    def on_round_end(self, context, round_results):
        """No special end‑of‑round logic; weekly totals reset automatically each round."""
        return None