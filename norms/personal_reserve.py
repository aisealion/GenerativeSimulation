# personal_reserve — each fisher must maintain a personal reserve of at least
# min_reserve_kg. If their reserve falls below this threshold, they are
# prohibited from fishing until their reserve is replenished.
#
# The reserve balance is read from runtime["payoff"][agent_id], which is the
# agent's running food balance updated by phases/harvest.py after each trip.
# This norm only enforces the minimum threshold rule; it does not modify the
# payoff balance (harvest.py handles that).
#
# Config:
#     {
#       "type": "personal_reserve",
#       "id": "personal_reserve",
#       "min_reserve_kg": 5.0   # minimum reserve required to be eligible to fish
#     }

from engine.norms.base import Norm, NormDecision


class PersonalReserveNorm(Norm):
    type_name = "personal_reserve"

    def _get_reserve(self, context, agent_id):
        """Get the agent's current reserve balance from payoff."""
        payoff = context.runtime.get("payoff", {})
        return payoff.get(agent_id, 0.0)

    def _get_min_reserve(self):
        """Get the minimum reserve threshold from params."""
        return self.params.get("min_reserve_kg", 5.0)

    def is_eligible(self, context, agent_id):
        """Agent is eligible only if their reserve >= min_reserve_kg."""
        reserve = self._get_reserve(context, agent_id)
        min_reserve = self._get_min_reserve()
        return reserve >= min_reserve

    def describe(self, context, agent_id):
        """Inform agent of their current reserve status."""
        reserve = self._get_reserve(context, agent_id)
        min_reserve = self._get_min_reserve()

        if reserve < min_reserve:
            shortfall = min_reserve - reserve
            return f"Your personal reserve is {reserve:.1f}kg, which is below the required {min_reserve:.0f}kg minimum. You must replenish {shortfall:.1f}kg before you can fish again."
        else:
            return f"Your personal reserve is {reserve:.1f}kg (minimum required: {min_reserve:.0f}kg)."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Allow the catch - this norm only affects eligibility, not catch amount.

        The operationalization says "Everyone may fish freely, keep all catch",
        so we don't modify the catch amount. We only control eligibility via
        is_eligible().
        """
        reserve = self._get_reserve(context, agent_id)
        min_reserve = self._get_min_reserve()

        # This should not happen if is_eligible() was checked, but handle it gracefully
        if reserve < min_reserve:
            return NormDecision.reject(
                reason=f"Your personal reserve ({reserve:.1f}kg) is below the minimum required ({min_reserve:.0f}kg). You cannot fish until your reserve is replenished."
            )

        return NormDecision.allow(proposed_kg)
