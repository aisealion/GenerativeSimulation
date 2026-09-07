"""
Round 10 norm implementing the updated policy from norm.txt.
Enforces per‑trip cap of 12 % of current stock (subject to 15 kg max) and a monthly cumulative cap of 30 % of the stock at the start of the month.
"""

from engine.norms.base import Norm, NormDecision


class MonthlyThirtyPercentNorm(Norm):
    """Round 10 norm implementation.

    * Per‑trip: up to 12 % of current lake stock, capped at 15 kg.
    * Monthly: cumulative catch may not exceed 30 % of the stock at month start.
    """

    type_name = "monthly_thirty_percent"

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Apply per‑trip and monthly caps.

        Steps:
        1. Compute per‑trip limit = min(0.12 * current_stock, 15.0).
        2. Trim kept kilograms to that limit.
        3. Update monthly totals and enforce the 30 % month‑start cap.
        """
        note_parts = []
        # current lake stock for this round (after regrowth, before harvest)
        current_stock = context.stock_before
        per_trip_cap = min(0.12 * current_stock, 15.0)
        kept_kg = raw_kg
        if kept_kg > per_trip_cap:
            kept_kg = per_trip_cap
            note_parts.append(f"trimmed to per‑trip cap {per_trip_cap:.2f} kg")

        # Monthly tracking – use round_scratch for this‑month accumulation
        monthly_state = context.round_scratch(self.key)
        month_start_stock = monthly_state.get("month_start_stock")
        if month_start_stock is None:
            # first agent of the month sets the reference stock
            month_start_stock = current_stock
            monthly_state["month_start_stock"] = month_start_stock
            monthly_state["monthly_total"] = 0.0
        monthly_total = monthly_state.get("monthly_total", 0.0)
        prospective_total = monthly_total + kept_kg
        month_cap = 0.30 * month_start_stock
        if prospective_total > month_cap:
            excess = prospective_total - month_cap
            kept_kg = max(kept_kg - excess, 0.0)
            note_parts.append(f"monthly cap exceeded, reduced by {excess:.2f} kg")
            violation = True
        else:
            violation = False
        # store updated total
        monthly_state["monthly_total"] = monthly_total + kept_kg

        note = ", ".join(note_parts) if note_parts else None
        if violation:
            return NormDecision.violation(kept_kg=kept_kg, note=note, sanction="monthly_limit_exceeded")
        else:
            return NormDecision.adjust(kept_kg=kept_kg, note=note)

    def on_round_end(self, context, round_results):
        """No special end‑of‑round logic for this norm."""
        return None
