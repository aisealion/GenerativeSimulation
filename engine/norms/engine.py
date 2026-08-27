# NormEngine: orchestrates every active Norm for one HarvestContext.
# Constructed fresh each round from state["config"]["norms"] via
# from_config(); phases/harvest.py owns exactly one NormEngine + one
# HarvestContext per round and threads both through the whole agent loop
# (never one-per-agent — see phases/harvest.py).

from engine.norms.base import NormDecision
from engine.norms.registry import load_norms


class NormEngine:
    def __init__(self, norms):
        self.norms = norms

    @classmethod
    def from_config(cls, config):
        return cls(load_norms(config))

    def start_round(self, context):
        for norm in self.norms:
            norm.on_round_start(context)

    def is_eligible(self, context, agent_id):
        """AND across every active norm — one veto is enough to skip the
        LLM call. Every norm's is_eligible() still runs regardless (a ban
        countdown must always tick), only the combined boolean result
        short-circuits the call."""
        eligible = True
        for norm in self.norms:
            if not norm.is_eligible(context, agent_id):
                eligible = False
        return eligible

    def describe_constraints(self, context, agent_id):
        lines = (norm.describe(context, agent_id) for norm in self.norms)
        return " ".join(line for line in lines if line)

    def ineligibility_note(self, context, agent_id):
        return self.describe_constraints(context, agent_id) or (
            "Something about the community's current rules held you back this round."
        )

    def apply(self, context, agent_id, raw_kg):
        """Threads raw_kg through every active norm's evaluate(), in config
        order — each norm sees the previous norm's kept_kg as its own
        proposed_kg, and raw_kg unchanged throughout (so a norm late in the
        chain, like reserve, can still compute "how much has been withheld
        by everyone before me" as raw_kg - proposed_kg without needing to
        know its own position). Folds every contributing norm's note
        (concatenated, in order) and first non-None sanction into one final
        NormDecision — a chain where two norms both intervened should
        surface both explanations, not just the last one. Then calls
        on_agent_settled() on every norm with that final decision."""
        kept_kg = raw_kg
        notes = []
        sanction = None
        violated = False
        for norm in self.norms:
            decision = norm.evaluate(context, agent_id, raw_kg, kept_kg)
            kept_kg = decision.kept_kg
            violated = violated or decision.violated
            if decision.note:
                notes.append(decision.note)
            if sanction is None and decision.sanction:
                sanction = decision.sanction

        final = NormDecision(
            kept_kg=kept_kg,
            note=" ".join(notes) or None,
            sanction=sanction,
            violated=violated,
        )
        for norm in self.norms:
            norm.on_agent_settled(context, agent_id, final, kept_kg)
        return final

    def end_round(self, context, round_results):
        for norm in self.norms:
            norm.on_round_end(context, round_results)
