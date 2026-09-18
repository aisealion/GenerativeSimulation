import json, os

def load_state():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../state/config.json'))
    with open(path) as f:
        return json.load(f)

def test_config_has_cap_rule_and_violation_rule():
    config = load_state()
    harvest_rules = config.get('rules', {}).get('harvest', [])
    assert any(r.get('type') == 'cap_rule' and r.get('cap_kg') == 15 for r in harvest_rules), "Cap rule with 15kg not configured"
    assert any(r.get('type') == 'violation_rule' for r in harvest_rules), "Violation rule not configured"

def test_communal_reserve_object_exists():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../state/objects.json'))
    with open(path) as f:
        objects = json.load(f)
    assert any(o.get('id') == 'communal_reserve' and o.get('type') == 'communal_reserve' for o in objects), "communal_reserve object missing"
