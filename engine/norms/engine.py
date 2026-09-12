# NormEngine: orchestrates every active Norm for one HarvestContext.
# Constructed fresh each round from state["config"]["norms"] via
# from_config(); actions/handlers/harvest.py owns exactly one NormEngine +
# one HarvestContext per round and threads both through the whole agent
# loop (never one-per-agent — see actions/handlers/harvest.py).

from engine.norms.base import NormDecision
from engine.norms.registry import load_norms
from engine.institution.lifecycle import tick
from roles.roles import end_fact


class NormEngine:
    def __init__(self, norms):
        self.norms = norms

    @classmethod
    def from_config(cls, config, round_number=None):
        """`round_number` is forwarded to load_norms() to filter out any
        norm whose own lifecycle has expired or not yet started — omit it
        (as every call site before lifecycle support existed still may)
        to get every configured norm regardless of activity."""
        return cls(load_norms(config, round_number))

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


def tick_norm_lifecycles(config, fluents, round_number):
    """Call once per round, before NormEngine.from_config() — closes any
    norm's norm_active fluent (see state/fluents_schema.md) the exact
    round its own "lifecycle" (state/config.json norms[i]["lifecycle"])
    naturally expires, so a norm given a bounded duration never needs the
    norm-implementer to hand-write termination logic or remember to close
    norm_active itself. A no-op for any norm with no lifecycle set (every
    norm before lifecycle support existed, and any norm meant to run
    indefinitely) — mutates `config`/`fluents` in place, same contract as
    every other state-mutating function in this project."""
    for spec in config.get("norms", []):
        lifecycle = spec.get("lifecycle")
        if not lifecycle:
            continue
        event = tick(lifecycle, round_number)
        if event is None:
            continue
        norm_type = spec.get("type")
        end_fact(
            fluents, "norm_active", {"type": norm_type}, round_number,
            narration=f"The rule covering {norm_type} has expired.",
            visibility="public", event_type="rule_deactivated",
        )
