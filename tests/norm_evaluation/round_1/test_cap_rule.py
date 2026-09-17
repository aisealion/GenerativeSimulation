import builtins
import types
from actions.rules.harvest.cap_rule import CapRule

class DummyObjects:
    def __init__(self):
        self.deposits = []
    def deposit(self, object_id, field, amount, by_agent_id=None, narration=None):
        # Record deposit calls for verification
        self.deposits.append({
            "object_id": object_id,
            "field": field,
            "amount": amount,
            "by_agent_id": by_agent_id,
            "narration": narration,
        })
        # Simulate returning new balance (not used)
        return amount

class DummyContext:
    def __init__(self):
        self.objects = DummyObjects()
        self.round_number = 1

def test_cap_rule_trims_harvest_and_deposits_surplus():
    ctx = DummyContext()
    rule = CapRule()
    # Simulate a record where harvested exceeds default cap (20kg)
    record = {"harvested_kg": 30.0, "note": None}
    # Call after_agent; should modify record in-place
    rule.after_agent(ctx, agent_id="agent_0", record_entry=record)
    assert record["harvested_kg"] == 20.0
    # Note should contain the trim message and surplus amount 10.0
    assert "Catch trimmed to 20kg cap" in record["note"]
    assert "10.0kg surplus" in record["note"]
    # Deposit should have been called for surplus
    assert len(ctx.objects.deposits) == 1
    dep = ctx.objects.deposits[0]
    assert dep["object_id"] == "communal_reserve"
    assert dep["field"] == "balance_kg"
    assert dep["amount"] == 10.0

def test_config_contains_cap_rule():
    import json
    config = json.loads((builtins.open('/home/magha601/code/GenerativeSimulation/state/config.json')).read())
    cap_rules = [r for r in config["rules"]["harvest"] if r["type"] == "cap_rule"]
    assert cap_rules, "CapRule entry not found in config"
    assert any(r.get("cap_kg") == 20 for r in cap_rules), "CapRule cap_kg is not set to 20"
