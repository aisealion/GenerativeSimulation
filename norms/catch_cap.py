"""Catch Cap Norm: Enforces a per-trip catch limit.

Policy: Each fisher may take no more than 5 kg per trip.
"""

from engine.norms.base import Norm, NormDecision


class CatchCapNorm(Norm):
    """Enforces a maximum catch limit per trip.

    If the proposed catch exceeds the limit, it is trimmed to the limit
    and marked as a violation with sanction "over_cap".
    """

    type_name = "catch_cap"

    def __init__(self, key, params):
        super().__init__(key, params)
        # Default to 5kg as per the policy, but allow configuration
        self.limit_kg = params.get("limit_kg", 5.0)

    def describe(self, context, agent_id):
        """Tell the agent about the catch limit."""
        return f"Community rules limit your catch to {self.limit_kg:.0f}kg per trip."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Trim catch to the limit if it exceeds it."""
        if proposed_kg <= self.limit_kg:
            return NormDecision.allow(proposed_kg)

        # Exceeds limit - trim and mark as violation
        excess = proposed_kg - self.limit_kg
        return NormDecision.violation(
            kept_kg=self.limit_kg,
            sanction="over_cap",
            note=f"Your catch exceeded the {self.limit_kg:.0f}kg limit; trimmed by {excess:.1f}kg."
        )
