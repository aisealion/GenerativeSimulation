from engine.norms.context import HarvestContext
from norms.catch_limit import CatchLimitNorm


def _context(stock=100.0):
    return HarvestContext.from_state({
        "config": {}, "fluents": [], "runtime": {"stock_kg": stock},
        "agents": {}, "round_number": 1,
    })


def test_flat_limit_trims_excess():
    norm = CatchLimitNorm(key="cap", params={"limit_kg": 10})
    decision = norm.evaluate(_context(), "agent_0", raw_kg=15.0, proposed_kg=15.0)
    assert decision.kept_kg == 10.0
    assert decision.violated is True
    assert decision.sanction == "over_cap"


def test_under_limit_is_unchanged():
    norm = CatchLimitNorm(key="cap", params={"limit_kg": 10})
    decision = norm.evaluate(_context(), "agent_0", raw_kg=5.0, proposed_kg=5.0)
    assert decision.kept_kg == 5.0
    assert decision.violated is False


def test_pct_of_stock_recomputes_from_current_stock():
    norm = CatchLimitNorm(key="cap", params={"limit_pct_of_stock": 0.1})
    decision = norm.evaluate(_context(stock=200.0), "agent_0", raw_kg=100.0, proposed_kg=100.0)
    assert decision.kept_kg == 20.0  # 10% of 200


def test_pct_wins_over_flat_when_both_set():
    norm = CatchLimitNorm(key="cap", params={"limit_kg": 999, "limit_pct_of_stock": 0.1})
    decision = norm.evaluate(_context(stock=100.0), "agent_0", raw_kg=50.0, proposed_kg=50.0)
    assert decision.kept_kg == 10.0


def test_per_agent_override_wins_over_flat_and_pct():
    norm = CatchLimitNorm(key="cap", params={
        "limit_kg": 999, "limit_pct_of_stock": 0.1, "limits_by_agent_kg": {"agent_0": 3},
    })
    decision = norm.evaluate(_context(stock=100.0), "agent_0", raw_kg=50.0, proposed_kg=50.0)
    assert decision.kept_kg == 3.0
    other = norm.evaluate(_context(stock=100.0), "agent_1", raw_kg=50.0, proposed_kg=50.0)
    assert other.kept_kg == 10.0  # non-overridden agent falls back to pct_of_stock (0.1 * 100)


def test_no_limit_configured_is_a_no_op():
    norm = CatchLimitNorm(key="cap", params={})
    decision = norm.evaluate(_context(), "agent_0", raw_kg=999.0, proposed_kg=999.0)
    assert decision.kept_kg == 999.0
    assert decision.violated is False


def test_describe_reports_current_limit():
    norm = CatchLimitNorm(key="cap", params={"limit_kg": 10})
    assert norm.describe(_context(), "agent_0") == "You currently have an agreed limit of 10kg for this trip."


def test_describe_none_when_no_limit():
    norm = CatchLimitNorm(key="cap", params={})
    assert norm.describe(_context(), "agent_0") is None
