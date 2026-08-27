# conditional_ban — a fishing ban that lifts when either a maximum duration
# elapses OR a monitored reserve is replenished (balance increases), whichever
# comes first.
#
# Config:
#     {
#       "type": "conditional_ban",
#       "id": "conditional_ban",
#       "trigger_sanction": "over_cap",      # which sanction starts a ban
#       "max_trips": 1,                      # max ban duration in trips/rounds
#       "reserve_norm_key": "reserve"        # key of the reserve norm to monitor
#     }
#
# The ban lifts early if the monitored reserve's balance increases from its
# level at ban-start (interpreted as "replenished"). If the balance never
# increases, the ban lasts exactly max_trips rounds.

from engine.norms.base import Norm, NormDecision


class ConditionalBanNorm(Norm):
    type_name = "conditional_ban"

    def _ban_state(self, context, agent_id):
        return context.norm_state(self.key).setdefault(
            agent_id, {"trips_remaining": 0, "balance_at_start": None}
        )

    def is_eligible(self, context, agent_id):
        ban = self._ban_state(context, agent_id)
        if ban["trips_remaining"] <= 0:
            return True

        # Check for early release: has the reserve been replenished?
        reserve_key = self.params.get("reserve_norm_key")
        if reserve_key:
            reserve_balance = context.norm_state(reserve_key).get("balance_kg", 0.0)
            balance_at_start = ban.get("balance_at_start")
            # Replenished = balance increased from when ban started
            if balance_at_start is not None and reserve_balance > balance_at_start:
                ban["trips_remaining"] = 0
                return True

        # Otherwise, decrement and check if ban is over
        ban["trips_remaining"] -= 1
        return ban["trips_remaining"] < 0

    def describe(self, context, agent_id):
        ban = self._ban_state(context, agent_id)
        remaining = ban["trips_remaining"]
        if remaining > 0:
            return f"You're currently suspended from fishing. The suspension will end after {remaining} more trip(s) or when the community reserve is replenished."
        return None

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        return NormDecision.allow(proposed_kg)  # banned agents never reach evaluate()

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        trigger = self.params.get("trigger_sanction")
        if trigger and decision.sanction == trigger:
            ban = self._ban_state(context, agent_id)
            ban["trips_remaining"] = self.params.get("max_trips", 1)
            # Record reserve balance at ban start for replenishment check
            reserve_key = self.params.get("reserve_norm_key")
            if reserve_key:
                balance = context.norm_state(reserve_key).get("balance_kg", 0.0)
                ban["balance_at_start"] = balance
