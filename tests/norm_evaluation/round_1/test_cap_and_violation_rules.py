import importlib
import json
import pathlib

# Structural checks

def test_cap_rule_exists():
    module = importlib.import_module('actions.rules.harvest.cap_rule')
    assert hasattr(module, 'CapRule')
    assert getattr(module.CapRule, 'type_name') == 'cap_rule'


def test_violation_rule_exists():
    module = importlib.import_module('actions.rules.harvest.violation_rule')
    assert hasattr(module, 'ViolationRule')
    assert getattr(module.ViolationRule, 'type_name') == 'violation_rule'


def test_config_has_cap_rule_with_20kg():
    config_path = pathlib.Path('state/config.json')
    config = json.loads(config_path.read_text())
    harvest_rules = config.get('rules', {}).get('harvest', [])
    # Find cap_rule entry
    cap_rule = next((r for r in harvest_rules if r.get('type') == 'cap_rule'), None)
    assert cap_rule is not None, "cap_rule not configured"
    assert cap_rule.get('cap_kg') == 20, "cap_kg should be 20"

# Functional checks – use the rule classes directly with a minimal context

class DummyObjects:
    def __init__(self):
        self.deposits = []

    def deposit(self, obj_type, field, amount, **kwargs):
        # Record deposit calls for verification
        self.deposits.append((obj_type, field, amount, kwargs))

class DummyCtx:
    def __init__(self):
        self.objects = DummyObjects()
        self.fluents = []  # list of fact dicts
        self.round_number = 1
        self._rule_states = {}

    def rule_state(self, key):
        # Return mutable dict per rule key
        return self._rule_states.setdefault(key, {})


def test_cap_rule_trims_and_deposits():
    # Import the rule class
    cap_module = importlib.import_module('actions.rules.harvest.cap_rule')
    rule = cap_module.CapRule(key='test_cap', params={'cap_kg': 20})
    ctx = DummyCtx()
    record = {'harvested_kg': 25, 'note': None}
    rule.after_agent(ctx, 'agent_0', record)
    # After trimming, harvested_kg should be capped at 20
    assert record['harvested_kg'] == 20
    # Note should mention the trim
    assert 'Catch trimmed' in record['note']
    # Surplus of 5 should be deposited to communal_reserve
    deposits = ctx.objects.deposits
    assert any(d[0] == 'communal_reserve' and d[1] == 'balance_kg' and d[2] == 5 for d in deposits)


def test_violation_rule_first_violation_creates_warning_fact_and_deposit():
    viol_module = importlib.import_module('actions.rules.harvest.violation_rule')
    rule = viol_module.ViolationRule(key='test_violation', params={})
    ctx = DummyCtx()
    # First call with a note indicating surplus triggers violation count 1
    record = {'note': 'surplus recorded'}
    rule.after_agent(ctx, 'agent_0', record)
    state = ctx.rule_state(rule.key)
    assert state.get('count') == 1
    # Should have deposited 5 kg penalty
    assert any(d[0] == 'communal_reserve' and d[2] == 5 for d in ctx.objects.deposits)
    # Fluents should contain a warning fact for the agent
    warning = next((f for f in ctx.fluents if f.get('fluent') == 'warning'), None)
    assert warning is not None
    assert warning['args'] == ['agent_0']


def test_violation_rule_second_violation_creates_ban_fact_and_deposit():
    viol_module = importlib.import_module('actions.rules.harvest.violation_rule')
    rule = viol_module.ViolationRule(key='test_violation2', params={})
    ctx = DummyCtx()
    # Simulate first violation to set count=1
    rule.after_agent(ctx, 'agent_0', {'note': 'surplus'})
    # Second violation should raise count to 2 and create a ban fact
    rule.after_agent(ctx, 'agent_0', {'note': 'surplus again'})
    state = ctx.rule_state(rule.key)
    assert state.get('count') == 2
    # Deposit should have been called twice (two penalties of 5kg each)
    assert sum(d[2] for d in ctx.objects.deposits) == 10
    ban = next((f for f in ctx.fluents if f.get('fluent') == 'ban'), None)
    assert ban is not None
    assert ban['args'] == ['agent_0']
