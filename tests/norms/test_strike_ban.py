from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.strike_ban import StrikeBanNorm


def _context(stock=100.0):
    return HarvestContext.from_state({
        "config": {}, "fluents": [], "runtime": {"stock_kg": stock},
        "agents": {}, "round_number": 1,
    })


def test_agent_is_eligible_by_default():
    """Agent should be eligible when they have no strikes."""
    norm = StrikeBanNorm(key="strike_ban", params={"trigger_sanction": "over_cap", "strikes": 3})
    assert norm.is_eligible(_context(), "agent_0") is True


def test_violation_increments_strike_count():
    """Each matching violation should increment the strike count."""
    context = _context()
    norm = StrikeBanNorm(key="strike_ban", params={"trigger_sanction": "over_cap", "strikes": 3})

    decision = NormDecision(kept_kg=10.0, sanction="over_cap", violated=True)

    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
    assert context.norm_state("strike_ban")["agent_0"]["strikes"] == 1

    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
    assert context.norm_state("strike_ban")["agent_0"]["strikes"] == 2


def test_non_matching_sanction_does_not_count():
    """Violations with different sanctions should not count as strikes."""
    context = _context()
    norm = StrikeBanNorm(key="strike_ban", params={"trigger_sanction": "over_cap", "strikes": 3})

    decision = NormDecision(kept_kg=10.0, sanction="other_violation", violated=True)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)

    # Agent state shouldn't be created if no matching violations
    assert "agent_0" not in context.norm_state("strike_ban")


def test_no_violation_does_not_count():
    """Non-violations should not increment strike count."""
    context = _context()
    norm = StrikeBanNorm(key="strike_ban", params={"trigger_sanction": "over_cap", "strikes": 3})

    decision = NormDecision(kept_kg=10.0, sanction=None, violated=False)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)

    # Agent state shouldn't be created if no matching violations
    assert "agent_0" not in context.norm_state("strike_ban")


def test_ban_triggered_after_threshold():
    """Ban should be triggered after specified number of strikes."""
    context = _context()
    norm = StrikeBanNorm(key="strike_ban", params={"trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2})

    decision = NormDecision(kept_kg=10.0, sanction="over_cap", violated=True)

    # First 2 strikes - no ban yet
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
    assert context.norm_state("strike_ban")["agent_0"]["ban_remaining"] == 0

    # Third strike triggers ban
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
    assert context.norm_state("strike_ban")["agent_0"]["ban_remaining"] == 2


def test_ban_blocks_eligibility():
    """When banned, agent should not be eligible."""
    context = _context()
    norm = StrikeBanNorm(key="strike_ban", params={"trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2})

    # Set up banned state directly
    context.norm_state("strike_ban")["agent_0"] = {"strikes": 3, "ban_remaining": 2}

    assert norm.is_eligible(context, "agent_0") is False


def test_ban_decrements_each_round():
    """Ban counter should decrement each round."""
    context = _context()
    norm = StrikeBanNorm(key="strike_ban", params={"trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2})

    # Set up banned state
    context.norm_state("strike_ban")["agent_0"] = {"strikes": 3, "ban_remaining": 2}

    # First call - decrements to 1, returns False
    assert norm.is_eligible(context, "agent_0") is False
    assert context.norm_state("strike_ban")["agent_0"]["ban_remaining"] == 1

    # Second call - decrements to 0, returns False
    assert norm.is_eligible(context, "agent_0") is False
    assert context.norm_state("strike_ban")["agent_0"]["ban_remaining"] == 0

    # Third call - now eligible again
    assert norm.is_eligible(context, "agent_0") is True


def test_ban_resets_strikes_when_complete():
    """After ban completes, strikes should be reset."""
    context = _context()
    norm = StrikeBanNorm(key="strike_ban", params={"trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2})

    # Set up banned state
    context.norm_state("strike_ban")["agent_0"] = {"strikes": 3, "ban_remaining": 1}

    # Call is_eligible to trigger decrement and reset
    norm.is_eligible(context, "agent_0")

    assert context.norm_state("strike_ban")["agent_0"]["strikes"] == 0
    assert context.norm_state("strike_ban")["agent_0"]["ban_remaining"] == 0


def test_describe_shows_warning_with_strikes():
    """describe() should warn agent when they have strikes."""
    context = _context()
    norm = StrikeBanNorm(key="strike_ban", params={"trigger_sanction": "over_cap", "strikes": 3})

    context.norm_state("strike_ban")["agent_0"] = {"strikes": 2, "ban_remaining": 0}

    description = norm.describe(context, "agent_0")
    assert "2 strike(s)" in description
    assert "1 more" in description  # 3 - 2 = 1 more for ban


def test_describe_shows_ban_status():
    """describe() should inform agent when they are banned."""
    context = _context()
    norm = StrikeBanNorm(key="strike_ban", params={"trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2})

    context.norm_state("strike_ban")["agent_0"] = {"strikes": 3, "ban_remaining": 2}

    description = norm.describe(context, "agent_0")
    assert "banned" in description.lower()
    assert "2 more trip(s)" in description


def test_describe_none_when_no_strikes():
    """describe() should return None when agent has no strikes."""
    context = _context()
    norm = StrikeBanNorm(key="strike_ban", params={"trigger_sanction": "over_cap", "strikes": 3})

    assert norm.describe(context, "agent_0") is None


def test_evaluate_always_allows():
    """evaluate() should always allow the catch (ban is in is_eligible)."""
    norm = StrikeBanNorm(key="strike_ban", params={"trigger_sanction": "over_cap", "strikes": 3})

    decision = norm.evaluate(_context(), "agent_0", raw_kg=20.0, proposed_kg=10.0)

    assert decision.kept_kg == 10.0
    assert decision.violated is False


def test_stricks_are_per_agent():
    """Strike counts should be tracked separately per agent."""
    context = _context()
    norm = StrikeBanNorm(key="strike_ban", params={"trigger_sanction": "over_cap", "strikes": 3})

    decision = NormDecision(kept_kg=10.0, sanction="over_cap", violated=True)

    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
    norm.on_agent_settled(context, "agent_1", decision, harvested_kg=10.0)

    assert context.norm_state("strike_ban")["agent_0"]["strikes"] == 2
    assert context.norm_state("strike_ban")["agent_1"]["strikes"] == 1
