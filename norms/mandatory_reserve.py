"""Mandatory Reserve Norm: Ensures each fisher maintains a minimum reserve.

Policy: Each fisher must keep a mandatory 1 kg reserve.
"""

from engine.norms.base import Norm, NormDecision


class MandatoryReserveNorm(Norm):
    """Ensures each fisher maintains a mandatory minimum reserve.

    The reserve is tracked per-agent. If a fisher's kept catch would leave
    them with less than the required reserve, it's a violation.
    """

    type_name = "mandatory_reserve"

    def __init__(self, key, params):
        super().__init__(key, params)
        # Default to 1kg as per the policy, but allow configuration
        self.reserve_kg = params.get("reserve_kg", 1.0)

    def describe(self, context, agent_id):
        """Tell the agent about the reserve requirement."""
        state = context.norm_state(self.key)
        current_reserve = state.get(agent_id, {}).get("reserve_kg", 0.0)
        return f"You must maintain a {self.reserve_kg:.0f}kg reserve (currently have {current_reserve:.1f}kg)."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Check if the fisher maintains the required reserve.

        The reserve is considered separately from the catch. If the fisher
        doesn't have the required reserve, mark as under_reserve violation.
        """
        state = context.norm_state(self.key)
        agent_state = state.setdefault(agent_id, {"reserve_kg": 0.0, "recorded": False})

        # First time - initialize reserve to the required amount
        if not agent_state["recorded"]:
            agent_state["reserve_kg"] = self.reserve_kg
            agent_state["recorded"] = True

        # Check if proposed catch would violate reserve
        # The fisher must keep at least reserve_kg, so they can only harvest
        # what exceeds the reserve
        available_to_harvest = max(0.0, proposed_kg - self.reserve_kg)

        if proposed_kg <= available_to_harvest + self.reserve_kg:
            # They're respecting the reserve
            return NormDecision.allow(proposed_kg)
        else:
            # They're trying to harvest into their reserve
            # This shouldn't normally happen if physics works correctly,
            # but we mark it as a violation
            return NormDecision.violation(
                kept_kg=available_to_harvest,
                sanction="under_reserve",
                note=f"You must maintain a {self.reserve_kg:.0f}kg reserve; your catch was adjusted."
            )

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Record the harvest in the ledger."""
        state = context.norm_state(self.key)
        agent_state = state.setdefault(agent_id, {"reserve_kg": self.reserve_kg, "recorded": True})

        # Update the ledger entry for this round
        ledger = state.setdefault("ledger", [])
        ledger.append({
            "agent_id": agent_id,
            "round": context.round_number,
            "harvested_kg": harvested_kg,
            "reserve_kg": agent_state["reserve_kg"],
            "violated": decision.violated,
        })
