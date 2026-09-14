import json
import copy
import pytest
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
from engine.institution.runtime import ActionRuntime
from engine.institution.context import ActionContext
from roles.roles import assign_role
import engine.physics as physics

# Helper to build state similar to baseline but with needed config and objects
def build_state(rules_config, stock_kg=300.0, assign_treasurer=False):
    # Load action spec
    with open('state/actions/harvest.json') as f:
        spec = json.load(f)
    # Minimal object type spec for communal_ledger
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
    if assign_treasurer:
        # assign treasurer role to agent_0 before the action runs
        assign_role("treasurer", "agent_0", state["fluents"], 1, exclusive=True, narration="test assign", visibility="public")
    return spec, state

def test_trip_cap_enforced(monkeypatch):
    # Configure rules: only trip_cap
    rules_config = [{"type": "trip_cap", "params": {"cap_kg": 15}}]
    spec, state = build_state(rules_config, assign_treasurer=True)
    # Monkeypatch catch_from_effort to exceed cap
    def fake_catch(effort, stock):
        return 20.0  # always above cap
    monkeypatch.setattr(physics, "catch_from_effort", fake_catch)
    # Monkeypatch call_fisher_agent to return max effort
    from engine import llm_agents as llm_agents_module
    def fake_call(agent_id, round_number, action_name, **fields):
        return {"effort": 1.0, "reasoning": "test"}
    monkeypatch.setattr(llm_agents_module, "call_fisher_agent", fake_call)

    record = ActionRuntime.run_action(spec, state, 1)
    # Verify harvested kg capped at 15 and note added
    agent0 = record["agents"]["agent_0"]
    assert agent0["harvested_kg"] == pytest.approx(15.0)
    assert "Trip cap applied" in agent0.get("note", "")
    # Ledger should have been withdrawn 5 kg
    ledger_bal = state["runtime"]["objects"]["communal_ledger"]["fields"]["balance_kg"]
    assert ledger_bal == pytest.approx(-5.0)
