# violation_ban — a multi-trip fishing ban for whoever the round's fully-
# chained NormDecision reports a matching sanction for. Persistent per-agent
# countdown at context.norm_state(key)[agent_id]["trips_remaining"].
#
# Config:
#     {
#       "type": "violation_ban",
#       "id": "violation_ban",
#       "trigger_sanction": "over_cap",  # which NormDecision.sanction starts a ban
#       "trips": 2                       # ban length, in rounds skipped
#     }
#
# The countdown decrements lazily, inside is_eligible() itself, exactly once
# per round (that method is called at most once per agent per round, from
# phases/harvest.py's run() loop) — this is what makes "trips": 2 mean
# "skipped for exactly 2 rounds", not 1: the round a violation happens the
# agent has already fished (the ban starts next round), and the ban ends the
# round after trips_remaining ticks down to 0.

from engine.norms.base import Norm, NormDecision


class ViolationBanNorm(Norm):
    type_name = "violation_ban"

    def _ban_state(self, context, agent_id):
        return context.norm_state(self.key).setdefault(agent_id, {"trips_remaining": 0})

    def is_eligible(self, context, agent_id):
        ban = self._ban_state(context, agent_id)
        if ban["trips_remaining"] > 0:
            ban["trips_remaining"] -= 1
            return False
        return True

    def describe(self, context, agent_id):
        remaining = self._ban_state(context, agent_id)["trips_remaining"]
        if remaining > 0:
            return f"You're currently banned from fishing for {remaining} more trip(s)."
        return None

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        return NormDecision.allow(proposed_kg)  # a banned agent never reaches evaluate()

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        trigger = self.params.get("trigger_sanction")
        if trigger and decision.sanction == trigger:
            self._ban_state(context, agent_id)["trips_remaining"] = self.params.get("trips", 1)
