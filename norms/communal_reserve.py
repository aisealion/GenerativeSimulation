"""
Norm implementing proposal 2:
- Per trip max 4 kg total catch.
- Up to 1 kg kept for personal sustenance; the remainder (up to 3 kg) is deposited into a communal reserve.
- The reserve balance is persisted across rounds via ``context.norm_state``.
- The norm adjusts the harvested amount accordingly and records a note.

This implementation focuses on the per‑trip constraints and reserve tracking;
the monthly 30 % biomass cap can be added later if needed.
"""

from engine.norms.base import Norm, NormDecision


class CommunalReserveNorm(Norm):
    """Enforce a 4 kg per‑trip cap with a 1 kg personal allowance.

    The norm:
    * Trims any catch above 4 kg.
    * Allows the fisher to keep at most 1 kg.
    * Deposits the remainder (up to 3 kg) into a communal reserve that is
      persisted in ``context.norm_state(self.key)`` under the key ``"reserve_kg"``.
    """

    type_name = "communal_reserve"

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        # Apply the absolute per‑trip cap of 4 kg.
        note_parts = []
        if raw_kg > 4.0:
            raw_kg = 4.0
            note_parts.append("trimmed to 4 kg trip limit")

        # Determine how much the fisher may keep (max 1 kg) and what goes to reserve.
        kept_kg = min(1.0, raw_kg)
        deposit_kg = raw_kg - kept_kg  # will be ≤ 3 kg

        # Persist the reserve balance.
        state = context.norm_state(self.key)
        state["reserve_kg"] = state.get("reserve_kg", 0.0) + deposit_kg

        if deposit_kg > 0:
            note_parts.append(f"deposited {deposit_kg:.2f} kg to communal reserve")

        note = ", ".join(note_parts) if note_parts else None
        return NormDecision.adjust(kept_kg=kept_kg, note=note)
