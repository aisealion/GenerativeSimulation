import json
import pytest
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
from engine.institution.runtime import ActionRuntime
from engine.institution.context import ActionContext
import engine.physics as physics

def build_state(rules_config, stock_kg=50.0):
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
        "config": {"rules": {"harvest": rules_config}},
        "fluents": [],
        "runtime": {"stock_kg": stock_kg, "rounds": [], "payoff": {}, "dead_agents": []},
        "agents": {
            "agent_0": {"name": "Kai", "personality_traits": ""},
            "agent_1": {"name": "Mara", "personality_traits": ""},
        },
        "object_types": {"communal_ledger": ledger_type},
        "objects": [{"id": "communal_ledger", "type": "communal_ledger"}],
        "round_number": 1,
    }
    return spec, state

def test_daily_cap_enforced(monkeypatch):
    # Configure only daily_cap rule (no params needed)
    rules_config = [{"type": "daily_cap"}]
    spec, state = build_state(rules_config, stock_kg=50.0)
    # Mock catch to be 30 kg each
    def fake_catch(effort, stock):
        return 30.0
    monkeypatch.setattr(physics, "catch_from_effort", fake_catch)
    # Mock call_fisher_agent to return max effort
    from engine import llm_agents as llm_agents_module
    def fake_call(agent_id, round_number, action_name, **fields):
        return {"effort": 1.0, "reasoning": "test"}
    monkeypatch.setattr(llm_agents_module, "call_fisher_agent", fake_call)
    record = ActionRuntime.run_action(spec, state, 1)
    # Cap = 0.2 * stock = 10 kg. Each agent total will be 30, excess 20, reduction should be min(recorded, excess) = 20? Actually reduction = min(harvested_kg, excess) = min(30,20)=20, so harvested_kg becomes 10.
    for aid in ["agent_0", "agent_1"]:
        agent = record["agents"][aid]
        assert agent["harvested_kg"] == pytest.approx(10.0)
        assert "Daily cap applied" in agent.get("note", "")
    # Ledger withdrawal 5kg per agent (total -10)
    ledger_bal = state["runtime"]["objects"]["communal_ledger"]["fields"]["balance_kg"]
    assert ledger_bal == pytest.approx(-10.0)
