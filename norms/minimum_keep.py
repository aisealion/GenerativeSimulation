# minimum_keep — ensure each fisher keeps at least 1kg per trip.
# Config (optional, no parameters needed):
#     {"type": "minimum_keep"}
# If a fisher's kept_kg after previous norms is below 1.0kg, this norm
# issues a violation (sanction "under_minimum") and returns 0kg kept.
# The violation can trigger a ban via a ViolationBanNorm with matching
# trigger_sanction.

from engine.norms.base import Norm, NormDecision


class MinimumKeepNorm(Norm):
    type_name = "minimum_keep"

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        # Enforce a floor of 1kg kept. If the agent's proposed keep is already
        # >= 1kg, allow it. Otherwise, issue a violation.
        if proposed_kg >= 1.0:
            return NormDecision.allow(proposed_kg)
        return NormDecision.violation(
            kept_kg=0.0,
            sanction="under_minimum",
            note="You must keep at least 1kg per trip; your catch was below this minimum.",
        )
