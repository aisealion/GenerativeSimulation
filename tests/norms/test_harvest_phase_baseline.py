import pytest

import phases.harvest as harvest_module
from engine.physics import apply_consumption, apply_regrowth, catch_from_effort

EFFORTS = {"agent_0": 0.5, "agent_1": 0.2}


def _fake_call_fisher_agent(agent_id, round_number, phase_name, **fields):
    return {"effort": EFFORTS[agent_id], "reasoning": "test"}


def _state(norms_config=None):
    return {
        "config": {"norms": norms_config or []},
        "fluents": [],
        "runtime": {"stock_kg": 300.0, "rounds": []},
        "agents": {
            "agent_0": {"name": "Kai", "personality_traits": ""},
            "agent_1": {"name": "Mara", "personality_traits": ""},
        },
        "round_number": 1,
    }


def test_baseline_empty_norms_matches_hand_computed_physics(monkeypatch):
    """With config["norms"] == [], HarvestPhase.run() must be pure physics —
    no cap, ban, or reserve logic anywhere in its path. This is the
    deterministic proof that the norm-plugin refactor preserves the
    pre-refactor (effort_cap-only, and with no cap configured) baseline
    behavior."""
    monkeypatch.setattr(harvest_module, "call_fisher_agent", _fake_call_fisher_agent)
    state = _state()

    record = harvest_module.PHASE.run(state)

    raw_0 = catch_from_effort(0.5, 300.0)
    raw_1 = catch_from_effort(0.2, 300.0)
    assert record["agents"]["agent_0"]["harvested_kg"] == pytest.approx(raw_0)
    assert record["agents"]["agent_1"]["harvested_kg"] == pytest.approx(raw_1)
    assert record["agents"]["agent_0"]["note"] is None
    assert record["agents"]["agent_1"]["note"] is None
    assert record["agents"]["agent_0"]["participated"] is True

    stock_after_harvest = 300.0 - (raw_0 + raw_1)
    assert record["stock_kg_after_harvest"] == pytest.approx(stock_after_harvest)
    assert record["stock_kg_after_regrowth"] == pytest.approx(apply_regrowth(stock_after_harvest))

    expected_payoff_0 = apply_consumption(0.0, raw_0)
    expected_payoff_1 = apply_consumption(0.0, raw_1)
    assert state["runtime"]["payoff"]["agent_0"] == pytest.approx(expected_payoff_0)
    assert state["runtime"]["payoff"]["agent_1"] == pytest.approx(expected_payoff_1)
    assert state["runtime"]["dead_agents"] == []


def test_baseline_no_norm_state_key_created_when_norms_empty(monkeypatch):
    monkeypatch.setattr(harvest_module, "call_fisher_agent", _fake_call_fisher_agent)
    state = _state()
    harvest_module.PHASE.run(state)
    assert "norms" not in state["runtime"]


def test_a_configured_norm_actually_constrains_the_result(monkeypatch):
    """Sanity check that config["norms"] is really wired through — not a
    baseline concern, but confirms the baseline test above isn't passing
    merely because norms are never consulted at all."""
    monkeypatch.setattr(harvest_module, "call_fisher_agent", _fake_call_fisher_agent)
    state = _state(norms_config=[{"type": "catch_limit", "limit_kg": 1.0}])

    record = harvest_module.PHASE.run(state)

    assert record["agents"]["agent_0"]["harvested_kg"] == pytest.approx(1.0)
    assert record["agents"]["agent_0"]["note"] is not None
    assert "1kg limit" in record["agents"]["agent_0"]["note"]


def test_ineligible_agent_skips_the_llm_call_entirely(monkeypatch):
    """The concrete skip-LLM-call proof: a banned agent must never reach
    call_fisher_agent — the whole point of the is_eligible() hook."""
    call_log = []

    def _tracking_call(agent_id, round_number, phase_name, **fields):
        call_log.append(agent_id)
        return {"effort": EFFORTS[agent_id], "reasoning": "test"}

    monkeypatch.setattr(harvest_module, "call_fisher_agent", _tracking_call)
    state = _state(norms_config=[
        {"type": "violation_ban", "trigger_sanction": "over_cap", "trips": 5},
    ])
    # Pre-seed agent_0 as already banned, as if a prior round's on_agent_settled() set it.
    state["runtime"].setdefault("norms", {}).setdefault("violation_ban", {})["agent_0"] = {
        "trips_remaining": 2
    }

    record = harvest_module.PHASE.run(state)

    assert "agent_0" not in call_log
    assert "agent_1" in call_log
    assert record["agents"]["agent_0"]["participated"] is False
    assert record["agents"]["agent_0"]["harvested_kg"] == 0.0
    assert record["agents"]["agent_0"]["effort"] is None
    assert record["agents"]["agent_0"]["note"] is not None
