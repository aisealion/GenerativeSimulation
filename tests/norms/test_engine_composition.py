from engine.norms.base import Norm, NormDecision
from engine.norms.context import HarvestContext
from engine.norms.engine import NormEngine


class _TrimByOne(Norm):
    """Stub: always trims 1kg off whatever it's handed, no note/sanction."""
    type_name = "_trim_by_one"

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        return NormDecision.allow(proposed_kg - 1)


class _ViolateIfOver(Norm):
    """Stub: rejects anything over its configured limit, with a note and sanction."""
    type_name = "_violate_if_over"

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        limit = self.params["limit"]
        if proposed_kg <= limit:
            return NormDecision.allow(proposed_kg)
        return NormDecision.violation(kept_kg=limit, sanction="_stub_sanction", note="trimmed by stub")


class _RecordsSettled(Norm):
    """Stub: records what on_agent_settled() was called with, for assertion."""
    type_name = "_records_settled"
    calls = []

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        return NormDecision.allow(proposed_kg - 100)  # obviously-intermediate value

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        _RecordsSettled.calls.append((agent_id, decision.kept_kg, harvested_kg))


def _context():
    return HarvestContext.from_state({
        "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
        "agents": {}, "round_number": 1,
    })


def test_apply_threads_kept_kg_through_norms_in_order():
    engine = NormEngine([_TrimByOne(key="a", params={}), _TrimByOne(key="b", params={})])
    decision = engine.apply(_context(), "agent_0", raw_kg=10.0)
    assert decision.kept_kg == 8.0


def test_apply_concatenates_notes_from_every_contributing_norm():
    n1 = _ViolateIfOver(key="n1", params={"limit": 100})  # never triggers
    n2 = _ViolateIfOver(key="n2", params={"limit": 5})    # triggers
    engine = NormEngine([n1, n2])
    decision = engine.apply(_context(), "agent_0", raw_kg=10.0)
    assert decision.note == "trimmed by stub"
    assert decision.violated is True


def test_apply_first_non_none_sanction_wins():
    n1 = _ViolateIfOver(key="n1", params={"limit": 1})
    n2 = _ViolateIfOver(key="n2", params={"limit": 1})
    engine = NormEngine([n1, n2])
    decision = engine.apply(_context(), "agent_0", raw_kg=10.0)
    assert decision.sanction == "_stub_sanction"


def test_apply_calls_on_agent_settled_with_final_not_intermediate_decision():
    _RecordsSettled.calls.clear()
    stub = _RecordsSettled(key="records", params={})
    engine = NormEngine([_TrimByOne(key="trim", params={}), stub])
    decision = engine.apply(_context(), "agent_0", raw_kg=10.0)
    assert _RecordsSettled.calls == [("agent_0", decision.kept_kg, decision.kept_kg)]
    assert decision.kept_kg == 10.0 - 1 - 100


def test_describe_constraints_joins_only_non_none():
    class _Silent(Norm):
        type_name = "_silent"

    class _Speaks(Norm):
        type_name = "_speaks"

        def describe(self, context, agent_id):
            return "hello"

    engine = NormEngine([_Silent(key="s", params={}), _Speaks(key="sp", params={})])
    assert engine.describe_constraints(_context(), "agent_0") == "hello"


def test_no_norms_is_a_pure_passthrough():
    engine = NormEngine([])
    decision = engine.apply(_context(), "agent_0", raw_kg=10.0)
    assert decision.kept_kg == 10.0
    assert decision.note is None
    assert decision.violated is False
