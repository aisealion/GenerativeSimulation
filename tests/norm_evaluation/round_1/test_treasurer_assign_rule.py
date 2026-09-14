import json
import pytest
from engine.institution.runtime import ActionRuntime
from engine.institution.context import ActionContext
from roles.roles import assign_role

def build_state(assign_treasurer=False):
    with open('state/actions/harvest.json') as f:
        spec = json.load(f)
    ledger_type = {
        "type_name": "communal_ledger",
        "description": "Ledger recording daily catches and pot balances",
        "ownership": "ROLE:treasurer",
        "fields": {"balance_kg": {"type": "number", "default": 0.0}},
        "operations": ["deposit", "withdraw", "read"],
        "permissions": {"WRITE": {"who": "ROLE:treasurer"}, "READ": {"who": "ALL"}},
        "custom_handler": None,
        "introduced_round": 1,
    }
    state = {
        "config": {"rules": {"harvest": [{"type": "treasurer_assign"}]}},
        "fluents": [],
        "runtime": {"stock_kg": 300.0, "rounds": [], "payoff": {}, "dead_agents": []},
        "agents": {
            "agent_0": {"name": "Kai", "personality_traits": ""},
            "agent_1": {"name": "Mara", "personality_traits": ""},
        },
        "object_types": {"communal_ledger": ledger_type},
        "objects": [{"id": "communal_ledger", "type": "communal_ledger"}],
        "round_number": 1,
    }
    if assign_treasurer:
        assign_role("treasurer", "agent_0", state["fluents"], 1, exclusive=True, narration="test assign", visibility="public")
    return spec, state

def test_treasurer_assign_rule(monkeypatch):
    spec, state = build_state(assign_treasurer=False)
    # Monkeypatch call_fisher_agent to dummy
    from engine import llm_agents as llm_agents_module
    def fake_call(agent_id, round_number, action_name, **fields):
        return {"effort": 0.5, "reasoning": "test"}
    monkeypatch.setattr(llm_agents_module, "call_fisher_agent", fake_call)
    # Run action
    record = ActionRuntime.run_action(spec, state, 1)
    # After action, treasurer should be assigned to the first logger (agent_0)
    # check fluents for role treasurer holder
    treasurer_fluent = next((f for f in state["fluents"] if f["fluent"] == "treasurer"), None)
    assert treasurer_fluent is not None
    assert treasurer_fluent["holder"] == "agent_0"
    # Ensure role assignment cleared after round (rule resets state)
    # Run second round with no first logger (no agents logged?) simulate by clearing records? We'll just check that rule_state cleared
    # after_action clears rule_state("treasurer_assign")
    assert state["runtime"]["rules"].get("treasurer_assign") == {}
