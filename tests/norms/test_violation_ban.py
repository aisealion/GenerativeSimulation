from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.violation_ban import ViolationBanNorm


def _context():
    return HarvestContext.from_state({
        "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
        "agents": {}, "round_number": 1,
    })


def test_matching_sanction_starts_a_ban():
    norm = ViolationBanNorm(key="ban", params={"trigger_sanction": "over_cap", "trips": 2})
    context = _context()
    decision = NormDecision(kept_kg=5.0, sanction="over_cap", violated=True)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=5.0)
    assert context.norm_state("ban")["agent_0"]["trips_remaining"] == 2


def test_non_matching_sanction_does_not_start_a_ban():
    norm = ViolationBanNorm(key="ban", params={"trigger_sanction": "over_cap", "trips": 2})
    context = _context()
    decision = NormDecision(kept_kg=5.0, sanction="something_else", violated=True)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=5.0)
    assert "agent_0" not in context.norm_state("ban")


def test_unsanctioned_agent_never_gets_a_norm_state_entry():
    norm = ViolationBanNorm(key="ban", params={"trigger_sanction": "over_cap", "trips": 2})
    context = _context()
    decision = NormDecision(kept_kg=5.0, sanction=None, violated=False)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=5.0)
    assert context.norm_state("ban") == {}


def test_ban_lasts_exactly_trips_rounds_no_off_by_one():
    """is_eligible() is only ever called once per agent per round, at the
    start of their turn — the violating round's own is_eligible() call
    already happened (and returned True) before on_agent_settled() set the
    countdown at the end of that same round, so it's not re-tested here.
    What this test proves is that the countdown started by on_agent_settled()
    blocks exactly the next `trips` rounds and no more."""
    norm = ViolationBanNorm(key="ban", params={"trigger_sanction": "over_cap", "trips": 2})
    context = _context()
    decision = NormDecision(kept_kg=5.0, sanction="over_cap", violated=True)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=5.0)

    # Next 2 rounds: skipped.
    assert norm.is_eligible(context, "agent_0") is False
    assert norm.is_eligible(context, "agent_0") is False

    # Round after that: eligible again.
    assert norm.is_eligible(context, "agent_0") is True


def test_is_eligible_decrements_exactly_once_per_call():
    norm = ViolationBanNorm(key="ban", params={})
    context = _context()
    context.norm_state("ban")["agent_0"] = {"trips_remaining": 3}
    norm.is_eligible(context, "agent_0")
    assert context.norm_state("ban")["agent_0"]["trips_remaining"] == 2


def test_describe_reports_remaining_trips():
    norm = ViolationBanNorm(key="ban", params={})
    context = _context()
    context.norm_state("ban")["agent_0"] = {"trips_remaining": 1}
    assert norm.describe(context, "agent_0") == "You're currently banned from fishing for 1 more trip(s)."


def test_describe_none_when_not_banned():
    norm = ViolationBanNorm(key="ban", params={})
    context = _context()
    assert norm.describe(context, "agent_0") is None
