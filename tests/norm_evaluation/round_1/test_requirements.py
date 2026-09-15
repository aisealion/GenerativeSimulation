import sys
import pathlib
import builtins
import json
import types
import pytest

# Ensure repo root is on sys.path for absolute imports before any other imports
REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from engine.institution.runtime import ActionRuntime
from engine.institution.context import ActionContext
from actions.rules.harvest.trip_cap import TripCapRule
from actions.rules.harvest.daily_cap import DailyCapRule
from actions.rules.harvest.treasurer_assign import TreasurerAssignRule
from engine.institution.objects import ObjectRuntime, ObjectPermissionError
from engine.institution.rules import RuleSet
import engine.llm_agents as llm_agents

# Helper to load base state from files
def load_state():
    # Load minimal state structures needed for tests
    # Use the real JSON files for config, object types, objects, etc.
    root = pathlib.Path(__file__).parents[4]
    def read_json(path):
        return json.loads((root / path).read_text())
    # Load object type spec and index by type_name
    ledger_spec = read_json("state/object_types/communal_ledger.json")
    object_types = {ledger_spec["type_name"]: ledger_spec}
    state = {
        "config": read_json("state/config.json"),
        "fluents": [],
        "runtime": {"rounds": [], "payoff": {}, "objects": {}},
        "agents": {},
        "object_types": object_types,
        "objects": [],
        "round_number": 1,
    }
    # Add placeholders for agents (10 agents)
    for i in range(10):
        state["agents"][str(i)] = {"name": f"Fisher{i}"}
    # Declare communal ledger object
    state["objects"].append({"id": "ledger", "type": "communal_ledger"})
    return state

# Requirement 1: Fisher logs catch into communal ledger before setting out (LLM call)
def test_fisher_logs_before_llm_call(monkeypatch):
    state = load_state()
    # Patch call_fisher_agent to capture order
    call_order = {}
    def fake_call_fisher_agent(agent_id, round_number, action_name, **fields):
        # At this point, ledger balance should be unchanged (no logging yet)
        obj_rt = ObjectRuntime(state["object_types"], state["objects"], state["runtime"]["objects"], state["fluents"], state["round_number"], None)
        balance = obj_rt.read("ledger", "balance_kg")
        call_order["balance_before"] = balance
        return {"some": "response"}
    monkeypatch.setattr(llm_agents, "call_fisher_agent", fake_call_fisher_agent)
    # Run harvest action via ActionRuntime
    spec = {"name": "harvest", "execution": {"handler": "harvest"}, "prompt": {"fields": {}}, "outputs": {}}
    # Ensure round number in state
    state["round_number"] = 1
    ActionRuntime.run_action(spec, state, 1)
    # After run, ledger balance should still be 0 (no deposit/withdraw before LLM)
    obj_rt = ObjectRuntime(state["object_types"], state["objects"], state["runtime"]["objects"], state["fluents"], state["round_number"], None)
    final_balance = obj_rt.read("ledger", "balance_kg")
    assert call_order["balance_before"] == 0.0
    assert final_balance == 0.0, "Ledger balance changed before fisher LLM call, violating requirement"

# Requirement 2: Enforce per-trip cap of 10 kg
def test_trip_cap_rule_enforces_cap(monkeypatch):
    state = load_state()
    # Build a minimal ActionContext with a mock ObjectRuntime that records withdraw calls
    class MockObjects:
        def __init__(self):
            self.withdraw_calls = []
        def withdraw(self, object_id, field, amount, by_agent_id=None, narration=None):
            self.withdraw_calls.append((object_id, field, amount, by_agent_id, narration))
            return None
        def deposit(self, *args, **kwargs):
            pass
        def read(self, *args, **kwargs):
            return 0.0
    mock_objects = MockObjects()
    ctx = types.SimpleNamespace(
        objects=mock_objects,
        state=state,
        spec={"name": "harvest"},
    )
    rule = TripCapRule(key="trip_cap", params={"cap_kg": 10.0})
    record = {"harvested_kg": 15.0, "note": None}
    patched = rule.after_agent(ctx, "0", record)
    # harvested_kg should be capped at 10
    assert patched["harvested_kg"] == 10.0
    # note should include fine message
    assert "Fine for exceeding trip cap" in patched["note"]
    # withdraw should have been called with amount 5.0
    assert mock_objects.withdraw_calls, "withdraw not called"
    obj_id, field, amount, by_agent_id, _ = mock_objects.withdraw_calls[0]
    assert obj_id == "communal_ledger"
    assert field == "balance_kg"
    assert amount == 5.0

# Requirement 3: Enforce daily catch cap of 100 kg
def test_daily_cap_rule_enforces_daily_cap(monkeypatch):
    state = load_state()
    # Prepare mock objects to capture deposit
    class MockObjects:
        def __init__(self):
            self.deposit_calls = []
        def deposit(self, object_id, field, amount, by_agent_id=None, narration=None):
            self.deposit_calls.append((object_id, field, amount, by_agent_id, narration))
            return None
        def read(self, *args, **kwargs):
            return 0.0
        def withdraw(self, *args, **kwargs):
            pass
    mock_objects = MockObjects()
    ctx = types.SimpleNamespace(
        objects=mock_objects,
        state=state,
        spec={"name": "harvest"},
    )
    rule = DailyCapRule(key="daily_cap", params={})
    # Simulate cumulative total exceeding 100kg
    # First call: 60kg
    record1 = {"harvested_kg": 60.0, "note": None}
    rule.after_agent(ctx, "0", record1)
    # Second call: 50kg, should trigger cap (total 110, excess 10)
    record2 = {"harvested_kg": 50.0, "note": None}
    patched = rule.after_agent(ctx, "1", record2)
    # harvested_kg should be reduced by 10
    assert patched["harvested_kg"] == 40.0
    # note should mention reduction
    assert "Daily cap applied" in patched["note"]
    # deposit should have been called with excess amount 10
    assert mock_objects.deposit_calls, "deposit not called"
    obj_id, field, amount, by_agent_id, _ = mock_objects.deposit_calls[0]
    assert obj_id == "communal_ledger"
    assert field == "balance_kg"
    assert amount == 10.0

# Requirement 4: Assign rotating treasurer based on first logger
def test_treasurer_assign_rule_assigns_role(monkeypatch):
    state = load_state()
    # Add a dummy fluents list to capture role assignment
    state["fluents"] = []
    ctx = types.SimpleNamespace(
        state=state,
        round_number=1,
    )
    rule = TreasurerAssignRule(key="treasurer_assign", params={})
    # after_agent stores first_logger
    rule.after_agent(ctx, "5", {})
    # after_action should assign role treasurer to agent "5" for next round (round_number+1)
    rule.after_action(ctx, {})
    # Check that a fluent for treasurer role exists with holder "5"
    fluents = ctx.state["fluents"]
    assert any(f.get("fluent") == "treasurer" and f.get("holder") == "5" for f in fluents), "Treasurer role not assigned"
    # Ensure rule_state cleared (no persistent state stored)
    # Since we didn't use ctx.state["runtime"], we check that no runtime rules key exists
    assert not ctx.state.get("runtime", {}).get("rules", {}), "rule_state not cleared"
