"""Tests for the conditional_ban norm implementing:
"Fisher who fails to follow the 20 kg limit is suspended from fishing for
one week or until the reserve is replenished."
"""

from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.conditional_ban import ConditionalBanNorm


def _context(runtime=None):
    return HarvestContext.from_state({
        "config": {},
        "fluents": [],
        "runtime": runtime or {"stock_kg": 100.0},
        "agents": {},
        "round_number": 1,
    })


def test_matching_sanction_starts_ban():
    """A sanction matching trigger_sanction starts a ban with max_trips remaining."""
    norm = ConditionalBanNorm(
        key="ban",
        params={"trigger_sanction": "over_cap", "max_trips": 1, "reserve_norm_key": "reserve"}
    )
    context = _context()
    decision = NormDecision(kept_kg=20.0, sanction="over_cap", violated=True)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=20.0)
    assert context.norm_state("ban")["agent_0"]["trips_remaining"] == 1


def test_non_matching_sanction_does_not_start_ban():
    """A non-matching sanction does not start a ban."""
    norm = ConditionalBanNorm(
        key="ban",
        params={"trigger_sanction": "over_cap", "max_trips": 1, "reserve_norm_key": "reserve"}
    )
    context = _context()
    decision = NormDecision(kept_kg=20.0, sanction="other_violation", violated=True)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=20.0)
    assert "agent_0" not in context.norm_state("ban")


def test_ban_lasts_max_trips_rounds_if_no_replenishment():
    """Without replenishment, ban lasts exactly max_trips rounds."""
    norm = ConditionalBanNorm(
        key="ban",
        params={"trigger_sanction": "over_cap", "max_trips": 2, "reserve_norm_key": "reserve"}
    )
    context = _context()
    # Set up reserve with some balance
    context.norm_state("reserve")["balance_kg"] = 10.0

    # Trigger ban
    decision = NormDecision(kept_kg=20.0, sanction="over_cap", violated=True)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=20.0)

    # Next 2 rounds: banned
    assert norm.is_eligible(context, "agent_0") is False
    assert norm.is_eligible(context, "agent_0") is False

    # Round after that: eligible again
    assert norm.is_eligible(context, "agent_0") is True


def test_ban_lifts_early_when_reserve_replenished():
    """Ban lifts before max_trips if reserve balance increases."""
    norm = ConditionalBanNorm(
        key="ban",
        params={"trigger_sanction": "over_cap", "max_trips": 5, "reserve_norm_key": "reserve"}
    )
    context = _context()
    # Set up reserve with initial balance
    context.norm_state("reserve")["balance_kg"] = 5.0

    # Trigger ban - records balance_at_start = 5.0
    decision = NormDecision(kept_kg=20.0, sanction="over_cap", violated=True)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=20.0)
    assert context.norm_state("ban")["agent_0"]["balance_at_start"] == 5.0

    # First check: still banned, decrements to 4
    assert norm.is_eligible(context, "agent_0") is False

    # Replenish the reserve (balance increases)
    context.norm_state("reserve")["balance_kg"] = 10.0

    # Next check: ban lifts because reserve was replenished
    assert norm.is_eligible(context, "agent_0") is True


def test_ban_does_not_lift_if_reserve_stays_same():
    """Ban continues if reserve balance does not increase."""
    norm = ConditionalBanNorm(
        key="ban",
        params={"trigger_sanction": "over_cap", "max_trips": 3, "reserve_norm_key": "reserve"}
    )
    context = _context()
    context.norm_state("reserve")["balance_kg"] = 5.0

    # Trigger ban
    decision = NormDecision(kept_kg=20.0, sanction="over_cap", violated=True)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=20.0)

    # Reserve stays same, not replenished
    for _ in range(2):
        assert norm.is_eligible(context, "agent_0") is False


def test_describe_reports_remaining_trips():
    """describe() reports the ban status with remaining trips."""
    norm = ConditionalBanNorm(
        key="ban",
        params={"trigger_sanction": "over_cap", "max_trips": 2, "reserve_norm_key": "reserve"}
    )
    context = _context()
    context.norm_state("reserve")["balance_kg"] = 0.0

    decision = NormDecision(kept_kg=20.0, sanction="over_cap", violated=True)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=20.0)

    desc = norm.describe(context, "agent_0")
    assert "suspended from fishing" in desc
    assert "2 more trip(s)" in desc  # max_trips=2, not decremented yet
    assert "community reserve is replenished" in desc


def test_describe_none_when_not_banned():
    """describe() returns None when agent is not banned."""
    norm = ConditionalBanNorm(
        key="ban",
        params={"trigger_sanction": "over_cap", "max_trips": 1, "reserve_norm_key": "reserve"}
    )
    context = _context()
    assert norm.describe(context, "agent_0") is None


def test_evaluate_allows_all():
    """evaluate() allows all catches since banned agents never reach it."""
    norm = ConditionalBanNorm(
        key="ban",
        params={"trigger_sanction": "over_cap", "max_trips": 1, "reserve_norm_key": "reserve"}
    )
    context = _context()
    decision = norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=20.0)
    assert decision.kept_kg == 20.0
    assert decision.violated is False


def test_ban_with_zero_max_trips():
    """max_trips=0 means no actual ban (eligible immediately)."""
    norm = ConditionalBanNorm(
        key="ban",
        params={"trigger_sanction": "over_cap", "max_trips": 0, "reserve_norm_key": "reserve"}
    )
    context = _context()
    decision = NormDecision(kept_kg=20.0, sanction="over_cap", violated=True)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=20.0)

    # Should be eligible immediately (no ban)
    assert norm.is_eligible(context, "agent_0") is True


def test_replenishment_detection_from_zero():
    """Ban lifts when reserve goes from 0 to positive (replenished from empty)."""
    norm = ConditionalBanNorm(
        key="ban",
        params={"trigger_sanction": "over_cap", "max_trips": 5, "reserve_norm_key": "reserve"}
    )
    context = _context()
    # Reserve starts at 0
    context.norm_state("reserve")["balance_kg"] = 0.0

    # Trigger ban
    decision = NormDecision(kept_kg=20.0, sanction="over_cap", violated=True)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=20.0)

    # First check: banned
    assert norm.is_eligible(context, "agent_0") is False

    # Replenish from 0 to positive
    context.norm_state("reserve")["balance_kg"] = 1.0

    # Ban lifts
    assert norm.is_eligible(context, "agent_0") is True
