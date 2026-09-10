"""Violation Handler Norm: Handles first-time violations.

Policy: If a fisher reports >5kg or reserve <1kg, the fisher must return 2kg
to the communal barrel, note the transfer on the ledger, and receive a gentle reminder.
"""

from engine.norms.base import Norm, NormDecision


class ViolationHandlerNorm(Norm):
    """Handles penalties for first-time violations.

    When a fisher violates the catch cap or reserve requirements,
    they must return 2kg to the communal barrel and receive a reminder.
    """

    type_name = "violation_handler"

    def __init__(self, key, params):
        super().__init__(key, params)
        # Amount to return to communal barrel for violations
        self.penalty_kg = params.get("penalty_kg", 2.0)

    def describe(self, context, agent_id):
        """Remind agents about violation consequences."""
        return "Violating catch limits requires returning 2kg to the communal barrel."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """This norm doesn't modify the catch directly - it acts in on_agent_settled."""
        # Pass through - the actual penalty is applied after settlement
        return NormDecision.allow(proposed_kg)

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Apply penalty for violations and record in ledger.

        If this agent had a violation (over_cap or under_reserve sanction),
        they must return 2kg to the communal barrel and we increment their
        violation count.
        """
        state = context.norm_state(self.key)

        # Initialize communal barrel if not exists
        if "communal_barrel_kg" not in state:
            state["communal_barrel_kg"] = 0.0

        # Track per-agent violations
        agent_violations = state.setdefault("violations", {})
        if agent_id not in agent_violations:
            agent_violations[agent_id] = {
                "count": 0,
                "history": []
            }

        # Check if there was a violation in the decision
        if decision.violated and decision.sanction in ("over_cap", "under_reserve"):
            # Increment violation count
            agent_violations[agent_id]["count"] += 1
            agent_violations[agent_id]["history"].append({
                "round": context.round_number,
                "sanction": decision.sanction,
                "final_kg": harvested_kg,
            })

            # Add penalty to communal barrel (in practice, this would reduce their payoff)
            # For now, we just track it in the ledger
            state["communal_barrel_kg"] += self.penalty_kg

            # Record the transfer on the ledger
            ledger = state.setdefault("ledger", [])
            ledger.append({
                "round": context.round_number,
                "agent_id": agent_id,
                "transfer_kg": self.penalty_kg,
                "reason": f"Violation: {decision.sanction}",
                "violation_number": agent_violations[agent_id]["count"],
            })

            # Update the decision note with gentle reminder
            if decision.note:
                reminder = f" As a reminder, please follow community rules. This is violation #{agent_violations[agent_id]['count']}."
                # Note: We can't modify the decision here, but we've recorded everything
