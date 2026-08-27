# The Norm strategy contract every plugin under norms/*.py implements, and
# the NormDecision shape evaluate() returns. Deliberately small and stable —
# if a new norm needs a new hook, that belongs in engine/norms/engine.py's
# NormEngine (which orchestrates these hooks), not here. Both files are
# human-owned; the norm-implementer's entire surface is top-level norms/.

from abc import ABC
from dataclasses import dataclass


@dataclass
class NormDecision:
    """The result of one norm's evaluate() call for one agent, or the final
    chained result of a whole round's NormEngine.apply(). kept_kg is the
    only field with unconditional meaning; note/sanction/violated are
    optional signals other norms (via engine chaining) and the round record
    (via results[agent_id]["note"]) can act on."""

    kept_kg: float
    note: str | None = None
    sanction: str | None = None
    violated: bool = False

    @classmethod
    def allow(cls, kept_kg):
        """No change — this norm has nothing to say about this catch."""
        return cls(kept_kg=kept_kg)

    @classmethod
    def adjust(cls, kept_kg, note=None):
        """A non-punitive change to kept_kg (a reserve top-up, e.g.) —
        distinct from violation() so a round's outcome doesn't read as a
        sanction just because some norm touched the number."""
        return cls(kept_kg=kept_kg, note=note)

    @classmethod
    def violation(cls, kept_kg, sanction=None, note=None):
        """A punitive reduction — over a cap, over a community allowance,
        etc. sanction is an opaque string other norms can key off (see
        norms/violation_ban.py's trigger_sanction) — not interpreted by the
        engine itself."""
        return cls(kept_kg=kept_kg, sanction=sanction, note=note, violated=True)

    @classmethod
    def reject(cls, reason=None):
        """This agent gets nothing from this trip at all."""
        return cls(kept_kg=0.0, note=reason, violated=True)


class Norm(ABC):
    """One active row of state["config"]["norms"]. Built fresh every round
    by engine.norms.registry.load_norms() — construction is cheap (just
    stores key/params); a norm never keeps state on self between calls,
    since a new instance exists every round. Cross-round-persistent state
    lives at context.norm_state(self.key) (backed by runtime["norms"][key],
    saved to state/runtime.json like every other simulation output);
    this-round-only state lives at context.round_scratch(self.key) (backed
    by the HarvestContext instance itself, never persisted)."""

    type_name: str = None  # set by every subclass; must be unique across norms/*.py

    def __init__(self, key, params):
        self.key = key
        self.params = params

    def is_eligible(self, context, agent_id):
        """False skips this agent's LLM call entirely this round (a live
        ban) — saves the cost/latency of asking someone who can't fish
        anyway. Called at most once per agent per round, from
        phases/harvest.py's run() loop; side effects here (a ban countdown
        tick) are safe precisely because of that single call site."""
        return True

    def describe(self, context, agent_id):
        """One already-in-world-phrased sentence describing whatever this
        norm currently has to say to this agent (a cap, a remaining
        allowance, a ban) — or None if it has nothing to say right now.
        HarvestPhase joins every active norm's non-None describe() output,
        in state["config"]["norms"] order, into one constraints_line prompt
        field — the generic replacement for the old hardcoded cap_line: it
        works for any combination of active norms without phases/harvest.py
        or prompts/phases/harvest.md ever needing to know which are active."""
        return None

    def on_round_start(self, context):
        """Once per round, before any agent is processed. For this-round
        setup only (context.round_scratch(self.key)) — persistent state
        should already reflect where last round left it."""
        return None

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Once per agent. raw_kg is the physics-only catch for this agent
        this round (constant through the whole chain); proposed_kg is what
        the previous norm in config order decided to keep (or raw_kg, for
        the first norm). Return a NormDecision for what *this* norm allows.
        Default: no opinion."""
        return NormDecision.allow(proposed_kg)

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Once per agent, after every active norm's evaluate() has run for
        them and harvested_kg (== decision.kept_kg, the final chained
        number) is settled. For side effects tied to this agent's own final
        outcome — a ban countdown starting because decision.sanction
        matched a trigger, say."""
        return None

    def on_round_end(self, context, round_results):
        """Once per round, after every agent has been processed.
        round_results: {agent_id: {"effort": float | None, "harvested_kg":
        float, "participated": bool, "note": str | None}} — the only hook
        that sees the whole round's outcome at once, for community-wide
        rules ("if total catch > 70% of stock, replenish"). May call
        context.override_stock_after_regrowth(kg)."""
        return None
