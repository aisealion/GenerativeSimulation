"""Norm plugin for round 4: 20 kg per trip cap, excess added to communal reserve, full forfeiture and 1‑month ban on exceedance."""

from engine.norms.base import Norm, NormDecision


class CapAndReserveNorm(Norm):
    """Enforces a 20 kg cap per trip.

    * If the raw catch <= 20 kg, the agent keeps it.
    * If the raw catch > 20 kg, the entire catch is added to a communal
      reserve (persisted via ``context.norm_state(self.key)``) and the agent
      receives a 1‑month fishing ban.
    """

    type_name = "cap_and_reserve"

    LIMIT_KG = 30.0
    BAN_KEY = "banned_until"
    RESERVE_KEY = "reserve_kg"
    BAN_DURATION = 1  # months (rounds)

    def is_eligible(self, context, agent_id):
        """Agents under an active ban are ineligible.

        The ban counter is stored as an integer number of remaining rounds.
        It is decremented each round in ``on_round_start``.
        """
        state = context.norm_state(self.key)
        remaining = state.get(self.BAN_KEY, {}).get(agent_id, 0)
        return remaining <= 0

    def on_round_start(self, context):
        """Decrement ban counters for all agents.

        Called once per round before any agents are processed.
        """
        state = context.norm_state(self.key)
        bans = state.setdefault(self.BAN_KEY, {})
        for agent in list(bans):
            if bans[agent] > 0:
                bans[agent] -= 1
        # Clean up zero entries
        for agent in [a for a, v in bans.items() if v <= 0]:
            del bans[agent]
        return None

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Apply the cap and reserve logic.

        * ``raw_kg`` is the physics‑computed catch.
        * ``proposed_kg`` is the amount passed from previous norms (or ``raw_kg``).
        """
        if raw_kg <= self.LIMIT_KG:
            # Within cap – keep the proposed amount (which should be ≤ limit)
            return NormDecision.allow(proposed_kg)
        # Exceeds cap – forfeit entire catch to reserve and ban the agent.
        # Update communal reserve.
        state = context.norm_state(self.key)
        reserve = state.get(self.RESERVE_KEY, 0.0)
        state[self.RESERVE_KEY] = reserve + raw_kg
        # Set ban for next month.
        bans = state.setdefault(self.BAN_KEY, {})
        bans[agent_id] = self.BAN_DURATION
        note = f"Catch of {raw_kg:.2f} kg exceeds {self.LIMIT_KG} kg limit; entire catch forfeited to communal reserve and a {self.BAN_DURATION}-month ban applied."
        return NormDecision.violation(kept_kg=0.0, sanction="ban_1_month", note=note)

    def describe(self, context, agent_id):
        """Provide a short description for the agent during the round.
        """
        return f"Maximum catch per trip is {self.LIMIT_KG} kg. Excess is added to the communal reserve; exceeding triggers a 1‑month ban."

    def on_round_end(self, context, round_results):
        """Optional: could spend reserve here; left as a no‑op for now.
        """
        return None
