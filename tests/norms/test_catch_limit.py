from engine.norms.context import HarvestContext
from norms.catch_limit import CatchLimitNorm


def _context(stock=100.0):
    return HarvestContext.from_state({
        "config": {}, "fluents": [], "runtime": {"stock_kg": stock},
        "agents": {}, "round_number": 1,
    })


def test_policy_limits_based_on_stock():
    norm = CatchLimitNorm(key="cap", params={})
    # Stock >=12 -> limit min(1.0kg, 3% of stock) = 0.45kg
    ctx = _context(stock=15.0)
    decision = norm.evaluate(ctx, "agent_0", raw_kg=2.0, proposed_kg=2.0)
    # Exceeds limit, entire catch forfeited
    assert decision.kept_kg == 0.0
    # Stock 9 -> limit 0.27kg, exceeds, forfeited
    ctx = _context(stock=9.0)
    decision = norm.evaluate(ctx, "agent_0", raw_kg=2.0, proposed_kg=2.0)
    assert decision.kept_kg == 0.0
    # Stock 7 -> limit 0.21kg, exceeds, forfeited
    ctx = _context(stock=7.0)
    decision = norm.evaluate(ctx, "agent_0", raw_kg=1.0, proposed_kg=1.0)
    assert decision.kept_kg == 0.0
    # Stock 5 -> suspension (limit 0, decision keeps 0)
    ctx = _context(stock=5.0)
    decision = norm.evaluate(ctx, "agent_0", raw_kg=1.0, proposed_kg=1.0)
    assert decision.kept_kg == 0.0


def test_describe_reports_current_limit():
    norm = CatchLimitNorm(key="cap", params={})
    ctx = _context(stock=12.0)
    # 3% of 12kg = 0.36kg
    assert norm.describe(ctx, "agent_0") == "You currently have an agreed limit of 0.36kg for this trip."
