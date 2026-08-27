# work_shift — a community work obligation imposed on fishers who fail to
# meet a minimum catch threshold. The affected fisher must work a community
# shift for a specified number of trips, during which they cannot fish.
#
# Config:
#     {
#       "type": "work_shift",
#       "id": "work_shift",
#       "min_catch_kg": 1.0,       # below this threshold triggers the obligation
#       "shift_trips": 2           # number of trips the work shift lasts
#     }
#
# Persistent per-agent state tracks remaining shift trips at
# context.norm_state(key)[agent_id]["trips_remaining"]. The shift starts
# the round after a low catch (the agent already fished this round), and
# prevents fishing for exactly shift_trips rounds.

from engine.norms.base import Norm, NormDecision


class WorkShiftNorm(Norm):
    type_name = "work_shift"

    def _shift_state(self, context, agent_id):
        return context.norm_state(self.key).setdefault(
            agent_id, {"trips_remaining": 0}
        )

    def is_eligible(self, context, agent_id):
        shift = self._shift_state(context, agent_id)
        if shift["trips_remaining"] > 0:
            shift["trips_remaining"] -= 1
            return False
        return True

    def describe(self, context, agent_id):
        remaining = self._shift_state(context, agent_id)["trips_remaining"]
        if remaining > 0:
            return f"You're working a community shift and cannot fish for {remaining} more trip(s)."
        return None

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        return NormDecision.allow(proposed_kg)

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        min_catch = self.params.get("min_catch_kg", 1.0)
        if harvested_kg < min_catch:
            shift = self._shift_state(context, agent_id)
            shift["trips_remaining"] = self.params.get("shift_trips", 2)
