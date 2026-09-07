"""
Full reserve norm implementing round 4 policy.
Features:
- Per‑trip cap of 4 kg, with up to 1 kg kept for sustenance and the remainder deposited to a communal reserve.
- Tracks each fisher's total catch for the round (treated as a month).
- Enforces a monthly catch limit of 10 % of the lake biomass. Any excess is returned and double‑deposited as a penalty.
- Updates the communal reserve accordingly at round end.
- Emits notes via NormDecision and records sanctions in the norm state for further processing.
"""

from engine.norms.base import Norm, NormDecision


class FullReserveNorm(Norm):
    """Round 4 norm implementation.

    * Per‑trip: max 4 kg total, keep at most 1 kg, deposit rest to reserve.
    * Monthly: total catch may not exceed 10 % of lake biomass. Excess is returned
      and double‑deposited as a penalty.
    """

    type_name = "full_reserve"

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Apply per‑trip constraints and record raw catch.

        * Trim to 4 kg trip limit.
        * Compute kept (≤1 kg) and deposit to reserve.
        * Store the post‑cap raw catch in round‑scratch for monthly accounting.
        """
        note_parts = []
        # enforce absolute per‑trip cap
        if raw_kg > 4.0:
            raw_kg = 4.0
            note_parts.append("trimmed to 4 kg trip limit")

        # keep up to 1 kg, rest goes to reserve
        kept_kg = min(1.0, raw_kg)
        deposit_kg = raw_kg - kept_kg

        # persist reserve balance
        state = context.norm_state(self.key)
        state["reserve_kg"] = state.get("reserve_kg", 0.0) + deposit_kg

        if deposit_kg > 0:
            note_parts.append(f"deposited {deposit_kg:.2f} kg to communal reserve")

        # record raw catch for monthly limit checking
        monthly = context.round_scratch(self.key)
        monthly.setdefault("catch_by_agent", {})
        monthly["catch_by_agent"][agent_id] = (
            monthly["catch_by_agent"].get(agent_id, 0.0) + raw_kg
        )

        note = ", ".join(note_parts) if note_parts else None
        return NormDecision.adjust(kept_kg=kept_kg, note=note)

    def on_round_end(self, context, round_results):
        """Enforce monthly 10 % biomass cap.

        The lake biomass at the start of the round is available as
        ``context.stock_before``. If an agent's total catch exceeds 10 % of that
        biomass, the excess is considered returned and double‑deposited to the
        reserve. A sanction note is added to the norm state for each violator.
        """
        # monthly catch tracking stored in round‑scratch
        monthly = context.round_scratch(self.key)
        catch_by_agent = monthly.get("catch_by_agent", {})
        if not catch_by_agent:
            return None

        biomass_limit = 0.10 * context.stock_before
        state = context.norm_state(self.key)
        for agent_id, total_catch in catch_by_agent.items():
            if total_catch > biomass_limit:
                excess = total_catch - biomass_limit
                penalty = excess * 2.0
                # add penalty to reserve
                state["reserve_kg"] = state.get("reserve_kg", 0.0) + penalty
                # record a sanction for this agent
                sanctions = state.setdefault("sanctions", {})
                sanctions[agent_id] = {
                    "excess": excess,
                    "penalty_deposited": penalty,
                }
        return None
