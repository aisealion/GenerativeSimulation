import pathlib
import re

from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.stock_and_catch_norm import StockAndCatchNorm


def test_norm_txt_length():
    content = pathlib.Path(__file__).resolve().parents[2] / "norm.txt"
    txt = content.read_text(encoding="utf-8")
    assert len(txt) >= 200, "norm.txt must be at least 200 characters"


def test_spec_contains_norm_name():
    spec = pathlib.Path(__file__).resolve().parents[3] / "state" / "norm_specs" / "round_12.md"
    spec_text = spec.read_text(encoding="utf-8")
    assert "stock_and_catch" in spec_text.lower(), "Spec missing norm name stock_and_catch"


def test_evaluate_catch_cap():
    ctx = HarvestContext.from_state({
        "config": {},
        "fluents": [],
        "runtime": {},
        "agents": {},
        "round_number": 1,
    })
    norm = StockAndCatchNorm(key="stock_and_catch", params={})
    # Over cap
    decision = norm.evaluate(ctx, "agent_0", raw_kg=10.0, proposed_kg=10.0)
    assert isinstance(decision, NormDecision)
    assert decision.kept_kg == 8.0
    assert decision.sanction == "catch_limit_exceeded"
    # Under cap
    decision2 = norm.evaluate(ctx, "agent_1", raw_kg=5.0, proposed_kg=5.0)
    assert decision2.kept_kg == 5.0
    assert decision2.sanction is None


def test_on_round_end_stock_violation():
    # Setup context with stock_before 100kg
    ctx = HarvestContext.from_state({
        "config": {},
        "fluents": [],
        "runtime": {},
        "agents": {},
        "round_number": 2,
    })
    ctx.stock_before = 100.0
    norm = StockAndCatchNorm(key="stock_and_catch", params={})
    # Simulate round results harvesting 80kg total (leaving 20kg < 30% of 100)
    round_results = {
        "agent_a": {"harvested_kg": 40.0, "participated": True},
        "agent_b": {"harvested_kg": 40.0, "participated": True},
    }
    norm.on_round_end(ctx, round_results)
    state = ctx.norm_state("stock_and_catch")
    assert "banned_agents" in state
    # Both agents should be banned for this round number
    assert state["banned_agents"]["agent_a"] == 2
    assert state["banned_agents"]["agent_b"] == 2
    # No stock violation when enough stock remains
    ctx2 = HarvestContext.from_state({
        "config": {},
        "fluents": [],
        "runtime": {},
        "agents": {},
        "round_number": 3,
    })
    ctx2.stock_before = 100.0
    norm.on_round_end(ctx2, {"agent_a": {"harvested_kg": 20.0, "participated": True}})
    state2 = ctx2.norm_state("stock_and_catch")
    assert "banned_agents" not in state2 or not state2.get("banned_agents")
