"""
Daily limit norm for round 6.
Enforces per‑trip maximum of 4 kg and a community‑wide daily total cap of 30 kg.
If an agent's catch would push the daily total above the cap, the excess is
removed from that agent's kept kilograms (down to zero) and a violation note is
recorded.
"""

from engine.norms.base import Norm, NormDecision


class DailyLimitNorm(Norm):
    """Round 6 norm implementation.

    * Per‑trip: max 4 kg total.
    * Daily community total: ≤30 kg. Excess is removed from the agent's
      kept catch and flagged as a violation.
    """

    type_name = "daily_limit"

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Apply per‑trip and daily limits.

        Steps:
        1. Enforce absolute per‑trip cap of 4 kg.
        2. Attempt to add the kept kilograms to the round‑wide daily total.
        3. If the daily total would exceed 30 kg, reduce the agent's kept
           kilograms accordingly and mark a violation.
        """
        note_parts = []
        # 1. per‑trip cap
        trimmed = raw_kg
        if trimmed > 4.0:
            trimmed = 4.0
            note_parts.append("trimmed to 4 kg trip limit")

        kept_kg = trimmed  # no reserve deposit for this norm

        # 2. daily total bookkeeping
        daily_state = context.round_scratch(self.key)
        daily_total = daily_state.get("daily_total", 0.0)
        prospective_total = daily_total + kept_kg
        violation = False
        if prospective_total > 30.0:
            # excess that must be removed from this agent's kept kg
            excess = prospective_total - 30.0
            kept_kg = max(kept_kg - excess, 0.0)
            violation = True
            note_parts.append(f"daily limit exceeded, reduced by {excess:.2f} kg")

        # update stored daily total with the final kept kg
        daily_state["daily_total"] = daily_total + kept_kg
        # optionally store per‑agent contribution for visibility
        per_agent = daily_state.setdefault("by_agent", {})
        per_agent[agent_id] = per_agent.get(agent_id, 0.0) + kept_kg

        note = ", ".join(note_parts) if note_parts else None
        if violation:
            return NormDecision.violation(kept_kg=kept_kg, note=note, sanction="daily_limit_exceeded")
        else:
            return NormDecision.adjust(kept_kg=kept_kg, note=note)

    def on_round_end(self, context, round_results):
        """No special end‑of‑round logic for this norm."""
        return None
