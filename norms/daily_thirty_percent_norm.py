"""
Policy 10 norm implementation (Round 15 winner).
Enforces:
* Per‑trip cap of 1.5 kg.
* Daily community total ≤ 30 % of lake stock at start of the day.
* If the daily cap is exceeded, the excess is removed from the fisher's kept kilograms,
  a violation is recorded, a $10 fee is added to the communal pool, and the fisher forfeits the right
  to fish on the next day (tracked as a sanction).
"""

from engine.norms.base import Norm, NormDecision


class DailyThirtyPercentNorm(Norm):
    """Daily‑limit norm for policy 10.

    * Per‑trip: max 1.5 kg total catch.
    * Daily community total: ≤ 30 % of the lake biomass at the start of the day.
    * Violation handling records a $10 fee and a one‑day fishing quota forfeiture.
    """

    type_name = "daily_thirty_percent"

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Apply per‑trip and daily limits.

        Steps:
        1. Enforce per‑trip cap of 1.5 kg.
        2. Enforce daily community cap of 30 % of the lake stock before harvest.
        3. If the daily cap would be exceeded, trim the fisher's kept kilograms,
           record a violation, add a $10 fee to the norm state, and note a forfeited
           day‑quota for the agent.
        """
        note_parts = []
        # 1. per‑trip cap
        trimmed = raw_kg
        if trimmed > 1.5:
            trimmed = 1.5
            note_parts.append("trimmed to 1.5 kg per‑trip limit")

        kept_kg = trimmed

        # 2. daily total bookkeeping (round is treated as a day)
        daily_state = context.round_scratch(self.key)
        daily_total = daily_state.get("daily_total", 0.0)
        daily_cap = 0.30 * context.stock_before  # 30 % of current stock
        prospective_total = daily_total + kept_kg
        violation = False
        if prospective_total > daily_cap:
            excess = prospective_total - daily_cap
            kept_kg = max(kept_kg - excess, 0.0)
            violation = True
            note_parts.append(f"daily limit exceeded, reduced by {excess:.2f} kg")

        # update stored daily total with the final kept kilograms
        daily_state["daily_total"] = daily_total + kept_kg

        if violation:
            # record the $10 fee and a forfeited‑quota sanction in norm state
            state = context.norm_state(self.key)
            state["fees_collected"] = state.get("fees_collected", 0.0) + 10.0
            forfeits = state.setdefault("forfeited_agents", {})
            forfeits[agent_id] = forfeits.get(agent_id, 0) + 1
            return NormDecision.violation(
                kept_kg=kept_kg,
                note=", ".join(note_parts),
                sanction="daily_limit_exceeded",
            )
        else:
            note = ", ".join(note_parts) if note_parts else None
            return NormDecision.adjust(kept_kg=kept_kg, note=note)

    def on_round_end(self, context, round_results):
        """No special end‑of‑round logic; daily totals reset automatically each round."""
        return None
