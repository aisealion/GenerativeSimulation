import pytest

import engine.institution.rules as rules_module
import engine.llm_agents as llm_agents_module
import actions.handlers.harvest as harvest_handler
from engine.institution.context import ActionContext
from engine.institution.rules import Rule
from engine.physics import apply_consumption, apply_regrowth, catch_from_effort

# The deterministic proof that harvest's own physics, plus the generic
# per-agent rule hooks (is_eligible/after_agent) every action now exposes,
# produce the exact numbers they always have — with no rule configured at
# all, and with one actually attached.

EFFORTS = {"agent_0": 0.5, "agent_1": 0.2}
SPEC = {"name": "harvest"}


def _fake_call_fisher_agent(agent_id, round_number, action_name, **fields):
    return {"effort": EFFORTS[agent_id], "reasoning": "test"}


def _state(rules_config=None):
    return {
        "config": {"rules": {"harvest": rules_config or []}},
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


def test_baseline_empty_rules_matches_hand_computed_physics(monkeypatch):
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


def test_baseline_no_rules_state_key_created_when_rules_empty(monkeypatch):
    monkeypatch.setattr(llm_agents_module, "call_fisher_agent", _fake_call_fisher_agent)
    state = _state()
    _run(state)
    assert "rules" not in state["runtime"]


class _FakeCap(Rule):
    type_name = "_fake_cap_for_handler_test"

    def after_agent(self, ctx, agent_id, record_entry):
        limit = self.params.get("limit_kg", 999999)
        if record_entry["harvested_kg"] > limit:
            return {"harvested_kg": limit, "note": f"trimmed to the {limit}kg limit"}
        return None


class _FakeBan(Rule):
    type_name = "_fake_ban_for_handler_test"

    def is_eligible(self, ctx, agent_id):
        return not ctx.rule_state(self.key).get(agent_id, False)


def _fake_discover(rule_types_by_action):
    return lambda action_name: rule_types_by_action.get(action_name, {})


def test_a_configured_rule_actually_constrains_the_result(monkeypatch):
    monkeypatch.setattr(llm_agents_module, "call_fisher_agent", _fake_call_fisher_agent)
    monkeypatch.setattr(
        rules_module, "discover_rule_types",
        _fake_discover({"harvest": {"_fake_cap_for_handler_test": _FakeCap}}),
    )
    state = _state(rules_config=[{"type": "_fake_cap_for_handler_test", "limit_kg": 1.0}])

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
    monkeypatch.setattr(
        rules_module, "discover_rule_types",
        _fake_discover({"harvest": {"_fake_ban_for_handler_test": _FakeBan}}),
    )
    state = _state(rules_config=[{"type": "_fake_ban_for_handler_test"}])
    state["runtime"].setdefault("rules", {}).setdefault("_fake_ban_for_handler_test", {})["agent_0"] = True

    record = _run(state)

    assert "agent_0" not in call_log
    assert "agent_1" in call_log
    assert record["agents"]["agent_0"]["participated"] is False
    assert record["agents"]["agent_0"]["harvested_kg"] == 0.0
    assert record["agents"]["agent_0"]["effort"] is None
    assert record["agents"]["agent_0"]["note"] is not None
