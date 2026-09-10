"""Catch Cap Norm: Enforces a per-trip catch limit.

Policy: Each fisher may take no more than 4 kg per trip. Surplus over
4kg must be deposited into the communal reserve held by Kai.
"""

from engine.norms.base import Norm, NormDecision


class CatchCapNorm(Norm):
    """Enforces a maximum catch limit per trip.

    If the proposed catch exceeds the limit, it is trimmed to the limit
    and marked as a violation with sanction "over_cap". The surplus
    (excess over 4kg) is deposited into the communal reserve.
    """

    type_name = "catch_cap"

    def __init__(self, key, params):
        super().__init__(key, params)
        # Default to 4kg as per round 4 policy, but allow configuration
        self.limit_kg = params.get("limit_kg", 4.0)

    def describe(self, context, agent_id):
        """Tell the agent about the catch limit."""
        return f"Community rules limit your catch to {self.limit_kg:.0f}kg per trip. Any surplus must be deposited into the communal reserve."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Trim catch to the limit if it exceeds it."""
        if proposed_kg <= self.limit_kg:
            return NormDecision.allow(proposed_kg)

        # Exceeds limit - trim and mark as violation
        excess = proposed_kg - self.limit_kg
        return NormDecision.violation(
            kept_kg=self.limit_kg,
            sanction="over_cap",
            note=f"Your catch exceeded the {self.limit_kg:.0f}kg limit; trimmed by {excess:.1f}kg. Surplus will be deposited to communal reserve."
        )

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Record violation details for tracking."""
        if not decision.violated or decision.sanction != "over_cap":
            return

        state = context.norm_state(self.key)

        # Extract excess from decision note
        excess_kg = 0.0
        if decision.note and "trimmed by " in decision.note:
            try:
                excess_str = decision.note.split("trimmed by ")[1].split("kg")[0]
                excess_kg = float(excess_str)
            except (IndexError, ValueError):
                excess_kg = 0.0

        # Record the violation
        violations = state.setdefault("violations", [])
        violations.append({
            "round": context.round_number,
            "agent_id": agent_id,
            "agent_name": context.agents.get(agent_id, {}).get("name", agent_id),
            "attempted_kg": harvested_kg + excess_kg,
            "allowed_kg": harvested_kg,
            "excess_kg": excess_kg,
        })
