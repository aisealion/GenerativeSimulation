import pytest

import engine.llm_agents as llm_agents_module
from engine.institution.context import ActionContext
from engine.institution.builtin_handlers import generic_agent_decision
from engine.institution.runtime import ActionRuntime

AGENTS = {
    "agent_0": {"name": "Kai", "personality_traits": ""},
    "agent_1": {"name": "Mara", "personality_traits": ""},
}


def _state(dead_agents=None):
    return {
        "config": {"favorite_spot_bonus": 1},
        "fluents": [],
        "runtime": {"stock_kg": 300.0, "rounds": [], "dead_agents": dead_agents or []},
        "agents": AGENTS,
        "round_number": 3,
    }


# A fully declarative Level 2 action: ask each alive fisher one question,
# record the answer verbatim under a renamed key — no actions/handlers/*.py
# file at all, proving generic_agent_decision genuinely needs zero custom
# code for this shape (unlike propose, which needs real cross-agent
# aggregation and so keeps its own small handler).
SIMPLE_SPEC = {
    "name": "favorite_spot",
    "execution": {"handler": "generic_agent_decision"},
    "prompt": {"fields": {
        "stock_kg": {"from": "state", "path": "runtime.stock_kg"},
        "bonus": {"from": "state", "path": "config.favorite_spot_bonus"},
    }},
    "outputs": {"per_agent_key": "answers", "fields": {"spot": "favorite_spot", "reasoning": "reasoning"}},
}


def test_generic_agent_decision_resolves_state_fields_and_calls_every_participant(monkeypatch):
    seen = {}

    def _fake_call(agent_id, round_number, action_name, **fields):
        seen[agent_id] = fields
        return {"spot": f"cove near {agent_id}", "reasoning": "nice and quiet"}

    monkeypatch.setattr(llm_agents_module, "call_fisher_agent", _fake_call)
    state = _state()
    ctx = ActionContext.build(SIMPLE_SPEC, state, state["round_number"])

    record = generic_agent_decision(ctx)

    assert set(seen) == {"agent_0", "agent_1"}
    assert seen["agent_0"] == {"stock_kg": 300.0, "bonus": 1}
    assert record == {
        "round": 3, "action": "favorite_spot",
        "answers": {
            "agent_0": {"favorite_spot": "cove near agent_0", "reasoning": "nice and quiet"},
            "agent_1": {"favorite_spot": "cove near agent_1", "reasoning": "nice and quiet"},
        },
    }


def test_generic_agent_decision_excludes_dead_agents(monkeypatch):
    monkeypatch.setattr(llm_agents_module, "call_fisher_agent",
                         lambda agent_id, round_number, action_name, **f: {"spot": "x"})
    state = _state(dead_agents=["agent_1"])
    ctx = ActionContext.build(SIMPLE_SPEC, state, state["round_number"])

    record = generic_agent_decision(ctx)

    assert set(record["answers"]) == {"agent_0"}


def test_generic_agent_decision_with_no_field_map_copies_response_verbatim(monkeypatch):
    monkeypatch.setattr(llm_agents_module, "call_fisher_agent",
                         lambda agent_id, round_number, action_name, **f: {"raw": 42})
    spec = {"name": "raw_action", "execution": {"handler": "generic_agent_decision"}}
    state = _state()
    ctx = ActionContext.build(spec, state, state["round_number"])

    record = generic_agent_decision(ctx)

    assert record["agents"]["agent_0"] == {"raw": 42}


def test_generic_agent_decision_reads_an_object_field_as_a_prompt_field(monkeypatch):
    monkeypatch.setattr(llm_agents_module, "call_fisher_agent",
                         lambda agent_id, round_number, action_name, **f: {"ack": True})
    spec = {
        "name": "check_pool",
        "execution": {"handler": "generic_agent_decision"},
        "prompt": {"fields": {"pool_balance": {"from": "object", "object_id": "reserve", "field": "balance_kg"}}},
    }
    state = _state()
    state["object_types"] = {"_pool": {"visibility": {"balance_kg": {"who": "ALL"}}}}
    state["objects"] = [{"id": "reserve", "type": "_pool"}]  # a declaration only
    state["runtime"]["objects"] = {"reserve": {"fields": {"balance_kg": 7.5}}}

    seen = {}

    def _fake_call(agent_id, round_number, action_name, **fields):
        seen[agent_id] = fields
        return {"ack": True}

    monkeypatch.setattr(llm_agents_module, "call_fisher_agent", _fake_call)
    ctx = ActionContext.build(spec, state, state["round_number"])
    generic_agent_decision(ctx)

    assert seen["agent_0"]["pool_balance"] == 7.5


def test_action_runtime_run_action_via_the_generic_builtin(monkeypatch):
    monkeypatch.setattr(llm_agents_module, "call_fisher_agent",
                         lambda agent_id, round_number, action_name, **f: {"spot": "x", "reasoning": ""})
    state = _state()

    record = ActionRuntime.run_action(SIMPLE_SPEC, state, state["round_number"])

    assert record["round"] == 3
    assert record["action"] == "favorite_spot"
    assert state["runtime"]["rounds"] == [record]


def test_unresolvable_handler_raises_a_clear_error():
    state = _state()
    spec = {"name": "nonexistent", "execution": {"handler": "does_not_exist"}}
    with pytest.raises(ValueError, match="neither a builtin"):
        ActionRuntime.run_action(spec, state, state["round_number"])
