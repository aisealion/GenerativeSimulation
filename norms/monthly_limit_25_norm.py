"""
Month 8 norm implementing updated policy.
Features:
- Per‑trip cap of 4 kg, must keep at least 1 kg for personal use.
- Monthly community catch limit of 25 % of lake stock at month start.
- If a fisher's total catch exceeds the monthly limit, the excess is returned and double‑deposited to the communal reserve.
- If a fisher records a total catch below 1 kg (i.e., cannot keep the mandatory personal keep), a violation is recorded and a sanction (ban) is applied.
"""

from engine.norms.base import Norm, NormDecision


class MonthlyLimit25Norm(Norm):
    """Round 8 norm implementation.

    * Per‑trip: max 4 kg total, must keep at least 1 kg for personal use.
    * Monthly: total catch may not exceed 25 % of lake biomass. Excess is returned and double‑deposited to reserve.
    * Violations for personal keep < 1 kg trigger a sanction.
    """

    type_name = "monthly_limit_25"

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Apply per‑trip constraints and record raw catch.

        * Enforce absolute per‑trip cap of 4 kg.
        * Ensure at least 1 kg is kept for personal use; otherwise record a violation.
        * Persist reserve balance for community portion.
        * Record raw catch for monthly accounting.
        """
        note_parts = []
        # enforce absolute per‑trip cap
        if raw_kg > 4.0:
            raw_kg = 4.0
            note_parts.append("trimmed to 4 kg trip limit")

        # must keep at least 1 kg for personal use
        if raw_kg < 1.0:
            # violation: cannot satisfy personal keep requirement
            note_parts.append("caught less than mandatory 1 kg personal keep")
            # keep zero, entire catch is forfeited
            kept_kg = 0.0
            # record violation with a generic sanction (e.g., "ban")
            decision = NormDecision.violation(kept_kg=kept_kg, sanction="ban", note=", ".join(note_parts))
            # still record for monthly accounting (the attempted catch)
            monthly = context.round_scratch(self.key)
            monthly.setdefault("catch_by_agent", {})
            monthly["catch_by_agent"][agent_id] = (
                monthly["catch_by_agent"].get(agent_id, 0.0) + raw_kg
            )
            return decision

        # keep at least 1 kg, rest goes to reserve
        kept_kg = 1.0
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
        """Enforce monthly 25 % biomass cap.

        The lake biomass at the start of the month is available as ``context.stock_before``.
        If an agent's total catch exceeds 25 % of that biomass, the excess is considered
        returned and double‑deposited to the reserve. A sanction note is added to the norm state
        for each violator.
        """
        monthly = context.round_scratch(self.key)
        catch_by_agent = monthly.get("catch_by_agent", {})
        if not catch_by_agent:
            return None

        biomass_limit = 0.25 * context.stock_before
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
