import pytest

from engine.norms.context import HarvestContext
from norms.round_4 import Round4Norm

@pytest.fixture
def base_state():
    return {
        "config": {
            "norms": [{"type_name": "round_4", "key": "round_4", "params": {}}]
        },
        "fluents": [],
        "runtime": {
            "norms": {"round_4": {"reserve_kg": 0.0}},
            "stock_kg": 100.0,
            "round": 1,
        },
        "agents": {},
        "round_number": 1,
    }

def make_context(state):
    return HarvestContext.from_state(state)

def test_within_quota_deposit_recorded(base_state):
    ctx = make_context(base_state)
    norm = Round4Norm("round_4", {})
    # raw catch well under quota (base quota = 18 kg)
    decision = norm.evaluate(ctx, agent_id="fish1", raw_kg=15.0, proposed_kg=15.0)
    assert decision.kept_kg == pytest.approx(15.0)
    # deposit = 5% of raw catch
    expected_deposit = 0.05 * 15.0
    deposits = ctx.round_scratch("round_4").get("deposits", [])
    assert deposits == [pytest.approx(expected_deposit)]
    # no over_quota recorded
    assert ctx.round_scratch("round_4").get("over_quota", []) == []

def test_over_quota_adjusts_and_records(base_state):
    ctx = make_context(base_state)
    norm = Round4Norm("round_4", {})
    # raw catch exceeds base quota (18 kg)
    decision = norm.evaluate(ctx, agent_id="fish2", raw_kg=30.0, proposed_kg=30.0)
    # adjusted quota = 18 kg (no streak yet)
    assert decision.kept_kg == pytest.approx(18.0)
    expected_deposit = 0.05 * 30.0
    deposits = ctx.round_scratch("round_4").get("deposits", [])
    assert deposits == [pytest.approx(expected_deposit)]
    over = ctx.round_scratch("round_4").get("over_quota", [])
    assert over == ["fish2"]

def test_streak_multiplier_and_state_persistence(base_state):
    # simulate a fisher with an existing streak of 1
    base_state["runtime"]["norms"]["round_4"]["fishA"] = {"streak": 1, "suspended": False}
    ctx = make_context(base_state)
    norm = Round4Norm("round_4", {})
    decision = norm.evaluate(ctx, agent_id="fishA", raw_kg=30.0, proposed_kg=30.0)
    # adjusted quota = 18 * 0.9 = 16.2
    assert decision.kept_kg == pytest.approx(16.2)
    # after round end, streak should increment to 2
    norm.on_round_end(ctx, round_results={"fishA": {}})
    state = ctx.norm_state("round_4")
    assert state["fishA"]["streak"] == 2
    assert state["fishA"]["suspended"] is False

def test_suspension_after_three_consecutive_over_quota(base_state):
    # start with streak 2
    base_state["runtime"]["norms"]["round_4"]["fishB"] = {"streak": 2, "suspended": False}
    ctx = make_context(base_state)
    norm = Round4Norm("round_4", {})
    decision = norm.evaluate(ctx, agent_id="fishB", raw_kg=30.0, proposed_kg=30.0)
    # adjusted quota = 18 * 0.9**2 = 14.58
    assert decision.kept_kg == pytest.approx(14.58)
    # round end should set suspended flag
    norm.on_round_end(ctx, round_results={"fishB": {}})
    state = ctx.norm_state("round_4")
    assert state["fishB"]["streak"] == 3
    assert state["fishB"]["suspended"] is True

def test_suspended_fisher_receives_violation_and_resets_next_round(base_state):
    # fisher already suspended
    base_state["runtime"]["norms"]["round_4"]["fishC"] = {"streak": 3, "suspended": True}
    ctx = make_context(base_state)
    norm = Round4Norm("round_4", {})
    decision = norm.evaluate(ctx, agent_id="fishC", raw_kg=20.0, proposed_kg=20.0)
    assert decision.kept_kg == pytest.approx(0.0)
    assert decision.sanction == "suspended"
    # deposit should be zero
    deposits = ctx.round_scratch("round_4").get("deposits", [])
    assert deposits == [0.0]
    # after round end, suspension flag cleared and streak reset
    norm.on_round_end(ctx, round_results={"fishC": {}})
    state = ctx.norm_state("round_4")
    assert state["fishC"]["streak"] == 0
    assert state["fishC"]["suspended"] is False
