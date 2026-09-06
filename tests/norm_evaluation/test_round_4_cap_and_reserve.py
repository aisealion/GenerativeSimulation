import pytest

from engine.norms.context import HarvestContext
from norms.cap_and_reserve import CapAndReserveNorm

AGENT_ID = "agent_0"


def make_state(round_number: int, runtime: dict):
    return {
        "config": {},
        "fluents": [],
        "runtime": runtime,
        "agents": {},
        "round_number": round_number,
    }


def test_cap_within_limit_allows_catch():
    runtime = {"norms": {}}
    ctx = HarvestContext.from_state(make_state(1, runtime))
    norm = CapAndReserveNorm(key="test", params={})
    decision = norm.evaluate(ctx, AGENT_ID, raw_kg=15.0, proposed_kg=15.0)
    assert decision.kept_kg == 15.0
    assert not decision.violated
    assert decision.sanction is None
    assert decision.note is None
    # No reserve or ban recorded
    assert runtime["norms"]["test"].get("reserve_kg", 0.0) == 0.0
    assert runtime["norms"]["test"].get("banned_until", {}) == {}


def test_cap_exceeds_limit_forfeits_and_bans():
    runtime = {"norms": {}}
    ctx = HarvestContext.from_state(make_state(1, runtime))
    norm = CapAndReserveNorm(key="test", params={})
    decision = norm.evaluate(ctx, AGENT_ID, raw_kg=30.0, proposed_kg=30.0)
    # Entire catch forfeited
    assert decision.kept_kg == 0.0
    assert decision.violated
    assert decision.sanction == "ban_1_month"
    assert "exceeds" in decision.note.lower()
    # Reserve updated and ban recorded
    state = runtime["norms"]["test"]
    assert state["reserve_kg"] == 30.0
    assert state["banned_until"][AGENT_ID] == 1


def test_ban_decrements_and_agent_becomes_eligible_next_round():
    runtime = {"norms": {}}
    # Round 1: exceed limit, creates ban
    ctx1 = HarvestContext.from_state(make_state(1, runtime))
    norm = CapAndReserveNorm(key="test", params={})
    norm.evaluate(ctx1, AGENT_ID, raw_kg=30.0, proposed_kg=30.0)
    # Round 2: start round should decrement ban counter
    ctx2 = HarvestContext.from_state(make_state(2, runtime))
    norm.on_round_start(ctx2)
    # After decrement, ban should be cleared
    state = runtime["norms"]["test"]
    assert state.get("banned_until", {}) == {}
    # Eligibility should now be True
    assert norm.is_eligible(ctx2, AGENT_ID) is True
