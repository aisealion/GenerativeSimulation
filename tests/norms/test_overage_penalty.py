from engine.norms.context import HarvestContext
from norms.overage_penalty import OveragePenaltyNorm


def _context(stock=100.0):
    return HarvestContext.from_state({
        "config": {}, "fluents": [], "runtime": {"stock_kg": stock},
        "agents": {}, "round_number": 1,
    })


def test_no_penalty_when_no_overage():
    """When proposed_kg equals raw_kg, no penalty applies."""
    norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})
    decision = norm.evaluate(_context(), "agent_0", raw_kg=10.0, proposed_kg=10.0)
    assert decision.kept_kg == 10.0
    assert decision.violated is False


def test_penalty_calculated_on_overage():
    """Penalty is 50% of the overage (raw - proposed)."""
    norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})
    # Agent tried to catch 20, was limited to 10 (e.g., by catch_limit)
    decision = norm.evaluate(_context(), "agent_0", raw_kg=20.0, proposed_kg=10.0)
    # Overage = 10, penalty = 5, final kept = 10 - 5 = 5
    assert decision.kept_kg == 5.0
    assert "penalty" in decision.note.lower()


def test_penalty_with_different_percentage():
    """Test with a different penalty percentage."""
    norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.25})
    decision = norm.evaluate(_context(), "agent_0", raw_kg=20.0, proposed_kg=10.0)
    # Overage = 10, penalty = 2.5, final kept = 10 - 2.5 = 7.5
    assert decision.kept_kg == 7.5


def test_penalty_tracks_in_community_fund():
    """Penalty amount should be tracked in the community fund."""
    context = _context()
    norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})

    decision = norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=10.0)

    # Check persistent fund
    fund = context.norm_state("penalty").get("community_fund", 0.0)
    assert fund == 5.0  # 50% of 10kg overage


def test_multiple_penalties_accumulate_in_fund():
    """Multiple penalties should accumulate in the community fund."""
    context = _context()
    norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})

    norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=10.0)  # 5kg penalty
    norm.evaluate(context, "agent_1", raw_kg=18.0, proposed_kg=10.0)  # 4kg penalty

    fund = context.norm_state("penalty").get("community_fund", 0.0)
    assert fund == 9.0  # 5 + 4


def test_custom_target_fund():
    """Penalty should go to custom target fund if specified."""
    context = _context()
    norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5, "target_fund": "lake_reserve"})

    norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=10.0)

    fund = context.norm_state("penalty").get("lake_reserve", 0.0)
    assert fund == 5.0


def test_penalty_never_goes_negative():
    """Final kept amount should never go below 0."""
    norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 1.0})  # 100% penalty
    decision = norm.evaluate(_context(), "agent_0", raw_kg=30.0, proposed_kg=10.0)
    # Overage = 20, penalty = 20, final kept = 10 - 20 = 0 (clamped)
    assert decision.kept_kg == 0.0


def test_describe_informs_about_penalty():
    """describe() should inform agents about the penalty rule."""
    norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})
    description = norm.describe(_context(), "agent_0")
    assert "50%" in description
    assert "penalty" in description.lower()


def test_describe_with_different_percentage():
    """describe() should reflect the configured penalty percentage."""
    norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.75})
    description = norm.describe(_context(), "agent_0")
    assert "75%" in description
