import pytest

import engine.norms.registry as registry
import engine.llm_agents as llm_agents_module
import actions.handlers.harvest as harvest_handler
from engine.institution.context import ActionContext
from engine.norms.base import Norm, NormDecision
from engine.physics import apply_consumption, apply_regrowth, catch_from_effort

# The exact same scenarios as tests/norms/test_harvest_action_baseline.py
# (which still exercises the old actions/harvest.py, kept in place until
# the Phase 3 cutover) — this is the deterministic proof that porting
# harvest's logic into actions/handlers/harvest.py, run through the new
# generic ActionRuntime/ActionContext, produces byte-identical output.

EFFORTS = {"agent_0": 0.5, "agent_1": 0.2}
SPEC = {"name": "harvest"}


def _fake_call_fisher_agent(agent_id, round_number, action_name, **fields):
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


def _run(state):
    ctx = ActionContext.build(SPEC, state, state["round_number"])
    return harvest_handler.run(ctx)


def test_baseline_empty_norms_matches_hand_computed_physics(monkeypatch):
    monkeypatch.setattr(llm_agents_module, "call_fisher_agent", _fake_call_fisher_agent)
    state = _state()

    record = _run(state)

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
    monkeypatch.setattr(llm_agents_module, "call_fisher_agent", _fake_call_fisher_agent)
    state = _state()
    _run(state)
    assert "norms" not in state["runtime"]


class _FakeCap(Norm):
    type_name = "_fake_cap_for_handler_test"

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        limit = self.params["limit_kg"]
        if proposed_kg <= limit:
            return NormDecision.allow(proposed_kg)
        return NormDecision.violation(kept_kg=limit, note=f"trimmed to the {limit}kg limit")


class _FakeBan(Norm):
    type_name = "_fake_ban_for_handler_test"

    def is_eligible(self, context, agent_id):
        return not context.norm_state(self.key).get(agent_id, False)


def test_a_configured_norm_actually_constrains_the_result(monkeypatch):
    monkeypatch.setattr(llm_agents_module, "call_fisher_agent", _fake_call_fisher_agent)
    monkeypatch.setattr(registry, "NORM_TYPES", {"_fake_cap_for_handler_test": _FakeCap})
    state = _state(norms_config=[{"type": "_fake_cap_for_handler_test", "limit_kg": 1.0}])

    record = _run(state)

    assert record["agents"]["agent_0"]["harvested_kg"] == pytest.approx(1.0)
    assert record["agents"]["agent_0"]["note"] is not None
    assert "1.0kg limit" in record["agents"]["agent_0"]["note"]


def test_ineligible_agent_skips_the_llm_call_entirely(monkeypatch):
    call_log = []

    def _tracking_call(agent_id, round_number, action_name, **fields):
        call_log.append(agent_id)
        return {"effort": EFFORTS[agent_id], "reasoning": "test"}

    monkeypatch.setattr(llm_agents_module, "call_fisher_agent", _tracking_call)
    monkeypatch.setattr(registry, "NORM_TYPES", {"_fake_ban_for_handler_test": _FakeBan})
    state = _state(norms_config=[{"type": "_fake_ban_for_handler_test"}])
    state["runtime"].setdefault("norms", {}).setdefault("_fake_ban_for_handler_test", {})["agent_0"] = True

    record = _run(state)

    assert "agent_0" not in call_log
    assert "agent_1" in call_log
    assert record["agents"]["agent_0"]["participated"] is False
    assert record["agents"]["agent_0"]["harvested_kg"] == 0.0
    assert record["agents"]["agent_0"]["effort"] is None
    assert record["agents"]["agent_0"]["note"] is not None
