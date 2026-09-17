import builtins
import json
from actions.rules.harvest.violation_rule import ViolationRule
from roles.roles import set_fact, end_fact

class DummyObjects:
    def __init__(self):
        self.deposits = []
    def deposit(self, object_id, field, amount, by_agent_id=None, narration=None):
        self.deposits.append({
            "object_id": object_id,
            "field": field,
            "amount": amount,
            "by_agent_id": by_agent_id,
            "narration": narration,
        })
        return amount

class DummyContext:
    def __init__(self):
        self.objects = DummyObjects()
        self.fluents = []
        self.round_number = 1
        self._rule_state = {}
    def rule_state(self, key):
        return self._rule_state.setdefault(key, {})

def test_violation_rule_no_violation():
    ctx = DummyContext()
    rule = ViolationRule("violation1", {})
    record = {"note": "All good", "harvested_kg": 10}
    rule.after_agent(ctx, agent_id="agent_0", record_entry=record)
    # No count increment, no deposits, no fluents
    assert ctx._rule_state["violation1"].get("count") is None
    assert ctx.objects.deposits == []
    assert ctx.fluents == []

def test_violation_rule_first_violation():
    ctx = DummyContext()
    rule = ViolationRule("violation1", {})
    record = {"note": "Surplus of fish", "harvested_kg": 30}
    rule.after_agent(ctx, agent_id="agent_0", record_entry=record)
    state = ctx._rule_state["violation1"]
    assert state["count"] == 1
    assert len(ctx.objects.deposits) == 1
    dep = ctx.objects.deposits[0]
    assert dep["object_id"] == "communal_reserve"
    assert dep["field"] == "balance_kg"
    assert dep["amount"] == 5
    # Warning fluent added
    warnings = [f for f in ctx.fluents if f["fluent"] == "warning"]
    assert warnings, "Warning fluent not recorded"
    assert warnings[0]["args"] == ["agent_0"]

def test_violation_rule_second_violation():
    ctx = DummyContext()
    rule = ViolationRule("violation1", {})
    # simulate first violation
    rule.after_agent(ctx, agent_id="agent_0", record_entry={"note": "Surplus", "harvested_kg": 30})
    # second violation
    rule.after_agent(ctx, agent_id="agent_0", record_entry={"note": "Surplus again", "harvested_kg": 30})
    state = ctx._rule_state["violation1"]
    assert state["count"] == 2
    # should have two deposits (one per violation)
    assert len(ctx.objects.deposits) == 2
    # Ban fluent added
    bans = [f for f in ctx.fluents if f["fluent"] == "ban"]
    assert bans, "Ban fluent not recorded"
    assert bans[0]["args"] == ["agent_0"]

def test_violation_rule_third_violation_permanent():
    ctx = DummyContext()
    rule = ViolationRule("violation1", {})
    # three violations
    rule.after_agent(ctx, agent_id="agent_0", record_entry={"note": "Surplus", "harvested_kg": 30})
    rule.after_agent(ctx, agent_id="agent_0", record_entry={"note": "Surplus", "harvested_kg": 30})
    rule.after_agent(ctx, agent_id="agent_0", record_entry={"note": "Surplus", "harvested_kg": 30})
    state = ctx._rule_state["violation1"]
    assert state["count"] == 3
    # Should have three deposits
    assert len(ctx.objects.deposits) == 3
    perma = [f for f in ctx.fluents if f["fluent"] == "permanent_ban"]
    assert perma, "Permanent ban fluent not recorded"
    assert perma[0]["args"] == ["agent_0"]
