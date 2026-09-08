import pytest

from engine.norms.context import HarvestContext
from norms.round_1 import Round1Norm

@pytest.fixture
def base_state():
    # Minimal viable simulation state for a norm test
    return {
        "config": {
            "norms": [
                {"type_name": "round_1", "key": "round_1", "params": {}}
            ]
        },
        "fluents": [],
        "runtime": {
            "norms": {"round_1": {"reserve_kg": 5.0}},
            "stock_kg": 100.0,
            "round": 1,
        },
        "agents": {},
    }

def make_context(state):
    return HarvestContext.from_state(state)

def test_deposit_applied(base_state):
    ctx = make_context(base_state)
    norm = Round1Norm("round_1", {})
    decision = norm.evaluate(ctx, agent_id="fish1", raw_kg=8.0, proposed_kg=8.0)
    # Deposit should be taken, kept = 8 - 2 = 6
    assert decision.kept_kg == pytest.approx(6.0)
    # Deposit recorded in round scratch
    deposits = ctx.round_scratch("round_1").get("deposits", [])
    assert deposits == [2.0]
    # No fine recorded
    assert ctx.round_scratch("round_1").get("fines", []) == []

def test_fine_applied_when_missing_deposit(base_state):
    ctx = make_context(base_state)
    norm = Round1Norm("round_1", {})
    # Raw catch below deposit threshold
    decision = norm.evaluate(ctx, agent_id="fish2", raw_kg=1.0, proposed_kg=1.0)
    # No deposit, fine should be 5% of 1kg = 0.05 (capped at 2kg)
    expected_fine = 0.05
    assert decision.kept_kg == pytest.approx(1.0)
    fines = ctx.round_scratch("round_1").get("fines", [])
    assert fines == [pytest.approx(expected_fine)]
    # No deposit recorded
    assert ctx.round_scratch("round_1").get("deposits", []) == []

def test_on_round_end_updates_reserve(base_state):
    ctx = make_context(base_state)
    norm = Round1Norm("round_1", {})
    # Simulate one agent with deposit and another with fine
    norm.evaluate(ctx, agent_id="a", raw_kg=8.0, proposed_kg=8.0)  # deposit 2
    norm.evaluate(ctx, agent_id="b", raw_kg=1.0, proposed_kg=1.0)  # fine 0.05
    # Before round end, reserve is 5.0
    assert ctx.norm_state("round_1")["reserve_kg"] == pytest.approx(5.0)
    # Apply round end aggregation
    norm.on_round_end(ctx, round_results=None)
    # New reserve should be old + deposits + fines = 5 + 2 + 0.05
    expected = 5.0 + 2.0 + 0.05
    assert ctx.norm_state("round_1")["reserve_kg"] == pytest.approx(expected)
