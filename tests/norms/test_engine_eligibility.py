from engine.norms.base import Norm
from engine.norms.context import HarvestContext
from engine.norms.engine import NormEngine


class _AlwaysEligible(Norm):
    type_name = "_always_eligible"


class _NeverEligible(Norm):
    type_name = "_never_eligible"

    def is_eligible(self, context, agent_id):
        return False


class _CountsCalls(Norm):
    """Confirms every norm's is_eligible() runs even after an earlier norm
    already vetoed — side effects (a ban countdown tick) must not be
    short-circuited."""
    type_name = "_counts_calls"
    call_count = 0

    def is_eligible(self, context, agent_id):
        _CountsCalls.call_count += 1
        return True


def _context():
    return HarvestContext.from_state({
        "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
        "agents": {}, "round_number": 1,
    })


def test_is_eligible_true_when_all_norms_agree():
    engine = NormEngine([_AlwaysEligible(key="a", params={})])
    assert engine.is_eligible(_context(), "agent_0") is True


def test_is_eligible_false_if_any_norm_vetoes():
    engine = NormEngine([_AlwaysEligible(key="a", params={}), _NeverEligible(key="b", params={})])
    assert engine.is_eligible(_context(), "agent_0") is False


def test_is_eligible_no_norms_defaults_true():
    engine = NormEngine([])
    assert engine.is_eligible(_context(), "agent_0") is True


def test_every_norm_is_eligible_still_runs_after_a_veto():
    _CountsCalls.call_count = 0
    engine = NormEngine([_NeverEligible(key="veto", params={}), _CountsCalls(key="counter", params={})])
    engine.is_eligible(_context(), "agent_0")
    assert _CountsCalls.call_count == 1


def test_ineligibility_note_falls_back_to_generic_when_norms_say_nothing():
    engine = NormEngine([_NeverEligible(key="veto", params={})])
    note = engine.ineligibility_note(_context(), "agent_0")
    assert note == "Something about the community's current rules held you back this round."


def test_ineligibility_note_prefers_a_norms_own_description():
    class _NeverEligibleWithReason(Norm):
        type_name = "_never_eligible_reason"

        def is_eligible(self, context, agent_id):
            return False

        def describe(self, context, agent_id):
            return "You are banned."

    engine = NormEngine([_NeverEligibleWithReason(key="veto", params={})])
    assert engine.ineligibility_note(_context(), "agent_0") == "You are banned."
