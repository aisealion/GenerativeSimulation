# keep — ensures each fisher keeps at least 1 kg per trip.

from engine.norms.base import Norm, NormDecision


class KeepNorm(Norm):
    type_name = "keep"

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """If the fisher keeps less than 1 kg, they must catch an extra kg next trip
        or pay a small fee to the reserve. We enforce the keep by allowing the
        current kept amount but attach a note.
        """
        if proposed_kg < 1.0:
            return NormDecision.adjust(
                kept_kg=proposed_kg,
                note="You must catch an extra kg next trip or pay a small fee to the reserve."
            )
        return NormDecision.allow(proposed_kg)