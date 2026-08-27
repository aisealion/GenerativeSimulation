from engine.norms.context import HarvestContext
from norms.sustenance_cap import SustenanceCapNorm


def _context(stock=100.0):
    return HarvestContext.from_state({
        "config": {}, "fluents": [], "runtime": {"stock_kg": stock},
        "agents": {}, "round_number": 1,
    })


def test_within_cap_allowed_unchanged():
    """Catch below 25% cap is allowed without modification."""
    norm = SustenanceCapNorm(key="cap", params={"limit_pct_of_stock": 0.25})
    # 25% of 100 = 25kg cap, proposing 20kg should be allowed
    decision = norm.evaluate(_context(stock=100.0), "agent_0", raw_kg=20.0, proposed_kg=20.0)
    assert decision.kept_kg == 20.0
    assert decision.violated is False


def test_exactly_at_cap_allowed():
    """Catch exactly at 25% cap is allowed."""
    norm = SustenanceCapNorm(key="cap", params={"limit_pct_of_stock": 0.25})
    decision = norm.evaluate(_context(stock=100.0), "agent_0", raw_kg=25.0, proposed_kg=25.0)
    assert decision.kept_kg == 25.0
    assert decision.violated is False


def test_over_cap_partial_release():
    """Excess over 25% cap results in 50% of excess being released."""
    norm = SustenanceCapNorm(key="cap", params={"limit_pct_of_stock": 0.25, "excess_release_fraction": 0.5})
    # Cap is 25kg, proposing 35kg = 10kg excess
    # Released = 10 * 0.5 = 5kg
    # Kept = 35 - 5 = 30kg
    decision = norm.evaluate(_context(stock=100.0), "agent_0", raw_kg=35.0, proposed_kg=35.0)
    assert decision.kept_kg == 30.0
    assert decision.violated is True
    assert decision.sanction == "over_cap"


def test_over_cap_with_custom_release_fraction():
    """Custom excess release fraction is respected."""
    norm = SustenanceCapNorm(key="cap", params={"limit_pct_of_stock": 0.25, "excess_release_fraction": 0.3})
    # Cap is 25kg, proposing 35kg = 10kg excess
    # Released = 10 * 0.3 = 3kg
    # Kept = 35 - 3 = 32kg
    decision = norm.evaluate(_context(stock=100.0), "agent_0", raw_kg=35.0, proposed_kg=35.0)
    assert decision.kept_kg == 32.0
    assert decision.violated is True


def test_cap_recomputed_from_current_stock():
    """25% cap is computed from current stock each round."""
    norm = SustenanceCapNorm(key="cap", params={"limit_pct_of_stock": 0.25})
    # 25% of 200 = 50kg cap
    decision = norm.evaluate(_context(stock=200.0), "agent_0", raw_kg=60.0, proposed_kg=60.0)
    # Excess = 60 - 50 = 10kg, released = 5kg, kept = 55kg
    assert decision.kept_kg == 55.0
    assert decision.violated is True


def test_custom_sanction_label():
    """Custom sanction label is used in violation."""
    norm = SustenanceCapNorm(key="cap", params={"limit_pct_of_stock": 0.25, "sanction": "custom_violation"})
    decision = norm.evaluate(_context(stock=100.0), "agent_0", raw_kg=30.0, proposed_kg=30.0)
    assert decision.violated is True
    assert decision.sanction == "custom_violation"


def test_default_sanction_is_over_cap():
    """Default sanction label is 'over_cap'."""
    norm = SustenanceCapNorm(key="cap", params={"limit_pct_of_stock": 0.25})
    decision = norm.evaluate(_context(stock=100.0), "agent_0", raw_kg=30.0, proposed_kg=30.0)
    assert decision.sanction == "over_cap"


def test_min_sustenance_floor_on_small_catch():
    """Fisher gets at least min_sustenance_kg even with very small catch."""
    norm = SustenanceCapNorm(key="cap", params={"limit_pct_of_stock": 0.25, "min_sustenance_kg": 1.0})
    decision = norm.evaluate(_context(stock=100.0), "agent_0", raw_kg=0.5, proposed_kg=0.5)
    # Should be adjusted up to 1kg minimum
    assert decision.kept_kg == 1.0
    assert decision.violated is False  # This is an adjustment, not a violation


def test_min_sustenance_does_not_affect_normal_catch():
    """min_sustenance_kg only kicks in when catch is below minimum."""
    norm = SustenanceCapNorm(key="cap", params={"limit_pct_of_stock": 0.25, "min_sustenance_kg": 1.0})
    decision = norm.evaluate(_context(stock=100.0), "agent_0", raw_kg=5.0, proposed_kg=5.0)
    assert decision.kept_kg == 5.0
    assert decision.violated is False


def test_min_sustenance_applies_to_violation():
    """Even with penalty, fisher keeps at least min_sustenance_kg."""
    norm = SustenanceCapNorm(key="cap", params={"limit_pct_of_stock": 0.25, "min_sustenance_kg": 1.0})
    # With very small stock (3kg), cap is 0.75kg which is below min_sustenance
    decision = norm.evaluate(_context(stock=3.0), "agent_0", raw_kg=2.0, proposed_kg=2.0)
    # Should keep at least 1kg despite penalty calculation
    assert decision.kept_kg >= 1.0


def test_describe_reports_current_cap():
    """describe() reports the current cap and sustenance minimum."""
    norm = SustenanceCapNorm(key="cap", params={"limit_pct_of_stock": 0.25, "min_sustenance_kg": 1.0})
    description = norm.describe(_context(stock=100.0), "agent_0")
    assert "25kg" in description or "25" in description
    assert "1kg" in description or "1" in description
    assert "sustenance" in description.lower()


def test_default_params():
    """Default params work correctly (25% cap, 1kg sustenance, 50% release)."""
    norm = SustenanceCapNorm(key="cap", params={})
    # 25% of 100 = 25kg default cap
    decision = norm.evaluate(_context(stock=100.0), "agent_0", raw_kg=35.0, proposed_kg=35.0)
    # Excess = 10kg, released = 5kg, kept = 30kg
    assert decision.kept_kg == 30.0
    assert decision.violated is True
