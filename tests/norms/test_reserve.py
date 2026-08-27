import pytest
from engine.norms.context import HarvestContext
from norms.reserve import ReserveNorm


def _context(runtime=None):
    return HarvestContext.from_state({
        "config": {}, "fluents": [], "runtime": runtime or {"stock_kg": 100.0},
        "agents": {}, "round_number": 1,
    })


def test_contributes_five_percent_and_deposits_full_catch_on_failure():
    # 5% contribution always added
    norm = ReserveNorm(key="reserve", params={})
    context = _context()
    # Agent keeps within limit (95% of raw)
    decision = norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=19.0)
    assert decision.kept_kg == 19.0
    # Balance should have 5% of raw added
    assert context.norm_state("reserve")["balance_kg"] == 1.0
    # Agent tries to keep more than allowed (fails to set aside 5%)
    decision_fail = norm.evaluate(context, "agent_1", raw_kg=10.0, proposed_kg=10.0)
    assert decision_fail.kept_kg == 0.0
    # Full catch (10) added to reserve in addition to prior balance (no extra 5% contribution)
    assert context.norm_state("reserve")["balance_kg"] == pytest.approx(1.0 + 10.0)

def test_withdrawal_tops_up_a_short_trip():
    norm = ReserveNorm(key="reserve", params={"shortfall_threshold_kg": 5, "max_withdrawal_kg": 4, "withdrawal_stock_threshold": 100})
    context = _context()
    # Set stock to trigger withdrawal condition
    context.stock_before = 90  # below custom 100
    context.norm_state("reserve")["balance_kg"] = 10.0
    decision = norm.evaluate(context, "agent_0", raw_kg=2.0, proposed_kg=2.0)
    # shortfall = threshold - proposed = 5-2=3, under max 4, so withdrawal 3
    assert decision.kept_kg == 2.0 + 3.0
    # balance after: initial 10 + contribution 0.1 then -3 withdrawal
    assert context.norm_state("reserve")["balance_kg"] == pytest.approx(10.0 - 3.0 + 0.1)

def test_withdrawal_capped_by_max_withdrawal_kg():
    norm = ReserveNorm(key="reserve", params={"shortfall_threshold_kg": 20, "max_withdrawal_kg": 2, "withdrawal_stock_threshold": 100})
    context = _context()
    context.stock_before = 90
    context.norm_state("reserve")["balance_kg"] = 100.0
    decision = norm.evaluate(context, "agent_0", raw_kg=1.0, proposed_kg=1.0)
    # withdrawal capped at 2, shortfall 19, so 2 withdrawn
    assert decision.kept_kg == 1.0 + 2.0
    assert context.norm_state("reserve")["balance_kg"] == pytest.approx(100.0 - 2.0 + 0.05)

def test_withdrawal_capped_by_available_balance():
    norm = ReserveNorm(key="reserve", params={"shortfall_threshold_kg": 20, "max_withdrawal_kg": 10, "withdrawal_stock_threshold": 100})
    context = _context()
    context.stock_before = 90
    context.norm_state("reserve")["balance_kg"] = 3.0
    decision = norm.evaluate(context, "agent_0", raw_kg=1.0, proposed_kg=1.0)
    assert decision.kept_kg == 1.0 + 3.0
    assert context.norm_state("reserve")["balance_kg"] == pytest.approx(0.0 + 0.05)

def test_no_withdrawal_when_balance_empty():
    norm = ReserveNorm(key="reserve", params={"shortfall_threshold_kg": 20, "withdrawal_stock_threshold": 100})
    context = _context()
    context.stock_before = 90
    decision = norm.evaluate(context, "agent_0", raw_kg=1.0, proposed_kg=1.0)
    assert decision.kept_kg == 1.0
    # only contribution added
    assert context.norm_state("reserve")["balance_kg"] == pytest.approx(0.05)

def test_no_withdrawal_when_above_stock_threshold():
    norm = ReserveNorm(key="reserve", params={"shortfall_threshold_kg": 5, "withdrawal_stock_threshold": 80})
    context = _context()
    context.stock_before = 100  # above threshold, no withdrawal
    context.norm_state("reserve")["balance_kg"] = 50.0
    decision = norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
    assert decision.kept_kg == 10.0
    assert context.norm_state("reserve")["balance_kg"] == pytest.approx(50.0 + 0.5)

def test_starting_balance_only_applies_once():
    norm = ReserveNorm(key="reserve", params={"starting_balance_kg": 10.0})
    context = _context()
    # First evaluation adds starting balance + contribution
    norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=9.5)
    # starting_balance 10 + contribution 0.5 = 10.5
    assert context.norm_state("reserve")["balance_kg"] == pytest.approx(10.5)

    # Simulate later round with persisted balance 2.0
    context.norm_state("reserve")["balance_kg"] = 2.0
    fresh_norm = ReserveNorm(key="reserve", params={"starting_balance_kg": 10.0})
    fresh_norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=9.5)
    # Should only add contribution 0.5, not starting_balance again
    assert context.norm_state("reserve")["balance_kg"] == pytest.approx(2.0 + 0.5)

def test_describe_reports_current_balance():
    norm = ReserveNorm(key="reserve", params={})
    context = _context()
    context.norm_state("reserve")["balance_kg"] = 7.0
    assert norm.describe(context, "agent_0") == "The community reserve currently holds 7kg."
