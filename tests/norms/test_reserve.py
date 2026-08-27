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
    # Deposit 0.5% of raw (0.075kg) + extra 0.5kg to meet reserve minimum
    assert decision.kept_kg == 15.0 - 0.075 - 0.5
    assert abs(context.norm_state("reserve")["balance_kg"] - (0.075 + 0.5)) < 1e-6


def test_no_excess_when_nothing_was_trimmed():
    norm = ReserveNorm(key="reserve", params={})
    context = _context()
    norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
    # Deposit 0.5% of raw (0.05kg) + extra 0.5kg
    assert abs(context.norm_state("reserve")["balance_kg"] - (0.05 + 0.5)) < 1e-6
    # Kept kg should reflect deposit and extra contribution
    # (not asserted here as decision not captured)


def test_withdrawal_capped_by_max_withdrawal_kg():
    norm = ReserveNorm(key="reserve", params={"shortfall_threshold_kg": 20, "max_withdrawal_kg": 2})
    context = _context()
    context.norm_state("reserve")["balance_kg"] = 100.0
    decision = norm.evaluate(context, "agent_0", raw_kg=1.0, proposed_kg=1.0)
    # Deposit 0.005kg, extra 0.5kg, then withdraw up to available balance (0.505kg) limited by max_withdrawal 2kg
    # After withdrawal, kept should be 1.0 (original) - deposit - extra + withdrawn = 1.0
    assert abs(decision.kept_kg - 1.0) < 1e-6
    # Balance should be 0 after withdrawing the 0.505kg added earlier
    assert abs(context.norm_state("reserve")["balance_kg"]) < 1e-6


def test_no_withdrawal_when_above_threshold():
    norm = ReserveNorm(key="reserve", params={"shortfall_threshold_kg": 5})
    context = _context()
    context.norm_state("reserve")["balance_kg"] = 50.0
    decision = norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
    # Deposit 0.05kg, extra 0.5kg, no withdrawal because kept (9.45kg) > threshold
    assert abs(decision.kept_kg - (10.0 - 0.05 - 0.5)) < 1e-6

def test_starting_balance_only_applies_once():
    norm = ReserveNorm(key="reserve", params={"starting_balance_kg": 10.0})
    context = _context()
    norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)  # no excess, first touch
    # Balance should be starting + deposit + extra
    expected_balance = 10.0 + 0.05 + 0.5
    assert abs(context.norm_state("reserve")["balance_kg"] - expected_balance) < 1e-6

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
