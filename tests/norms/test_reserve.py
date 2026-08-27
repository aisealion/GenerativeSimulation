from engine.norms.context import HarvestContext
from norms.reserve import ReserveNorm


def _context(runtime=None):
    return HarvestContext.from_state({
        "config": {}, "fluents": [], "runtime": runtime or {"stock_kg": 100.0},
        "agents": {}, "round_number": 1,
    })


def test_deposits_the_trimmed_excess():
    norm = ReserveNorm(key="reserve", params={})
    context = _context()
    # raw_kg=15, proposed_kg=10 -> an earlier cap norm already trimmed 5kg
    decision = norm.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=10.0)
    assert decision.kept_kg == 10.0
    assert context.norm_state("reserve")["balance_kg"] == 5.0


def test_no_excess_when_nothing_was_trimmed():
    norm = ReserveNorm(key="reserve", params={})
    context = _context()
    norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
    assert context.norm_state("reserve")["balance_kg"] == 0.0


def test_withdrawal_tops_up_a_short_trip():
    norm = ReserveNorm(key="reserve", params={"shortfall_threshold_kg": 5, "max_withdrawal_kg": 4})
    context = _context()
    context.norm_state("reserve")["balance_kg"] = 10.0
    decision = norm.evaluate(context, "agent_0", raw_kg=2.0, proposed_kg=2.0)
    # shortfall = threshold - proposed_kg = 5 - 2 = 3, under max_withdrawal_kg=4, so 3 is the binding limit
    assert decision.kept_kg == 2.0 + 3.0
    assert context.norm_state("reserve")["balance_kg"] == 10.0 - 3.0


def test_withdrawal_capped_by_max_withdrawal_kg():
    norm = ReserveNorm(key="reserve", params={"shortfall_threshold_kg": 20, "max_withdrawal_kg": 2})
    context = _context()
    context.norm_state("reserve")["balance_kg"] = 100.0
    decision = norm.evaluate(context, "agent_0", raw_kg=1.0, proposed_kg=1.0)
    assert decision.kept_kg == 1.0 + 2.0
    assert context.norm_state("reserve")["balance_kg"] == 98.0


def test_withdrawal_capped_by_available_balance():
    norm = ReserveNorm(key="reserve", params={"shortfall_threshold_kg": 20, "max_withdrawal_kg": 10})
    context = _context()
    context.norm_state("reserve")["balance_kg"] = 3.0
    decision = norm.evaluate(context, "agent_0", raw_kg=1.0, proposed_kg=1.0)
    assert decision.kept_kg == 1.0 + 3.0
    assert context.norm_state("reserve")["balance_kg"] == 0.0


def test_no_withdrawal_when_balance_empty():
    norm = ReserveNorm(key="reserve", params={"shortfall_threshold_kg": 20})
    context = _context()
    decision = norm.evaluate(context, "agent_0", raw_kg=1.0, proposed_kg=1.0)
    assert decision.kept_kg == 1.0


def test_no_withdrawal_when_above_threshold():
    norm = ReserveNorm(key="reserve", params={"shortfall_threshold_kg": 5})
    context = _context()
    context.norm_state("reserve")["balance_kg"] = 50.0
    decision = norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
    assert decision.kept_kg == 10.0
    assert context.norm_state("reserve")["balance_kg"] == 50.0


def test_starting_balance_only_applies_once():
    norm = ReserveNorm(key="reserve", params={"starting_balance_kg": 10.0})
    context = _context()
    norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)  # no excess, first touch
    assert context.norm_state("reserve")["balance_kg"] == 10.0

    # Simulate a later round reusing the same persisted runtime state: a
    # fresh Norm instance (as load_norms() creates every round) must not
    # re-apply starting_balance_kg on top of what's already accumulated.
    context.norm_state("reserve")["balance_kg"] = 2.0
    fresh_norm = ReserveNorm(key="reserve", params={"starting_balance_kg": 10.0})
    fresh_norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
    assert context.norm_state("reserve")["balance_kg"] == 2.0


def test_describe_reports_current_balance():
    norm = ReserveNorm(key="reserve", params={})
    context = _context()
    context.norm_state("reserve")["balance_kg"] = 7.0
    assert norm.describe(context, "agent_0") == "The community reserve currently holds 7kg."
