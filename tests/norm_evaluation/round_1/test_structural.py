import json
import os

def test_config_has_cap_rule():
    config_path = os.path.join(os.path.dirname(__file__), '../../../state/config.json')
    with open(os.path.abspath(config_path), 'r') as f:
        config = json.load(f)
    harvest_rules = config.get('rules', {}).get('harvest', [])
    assert any(r.get('type') == 'cap_rule' and r.get('cap_kg') == 20 for r in harvest_rules), "Cap rule with 20kg not configured"

def test_institution_rule_types_registered():
    institution_path = os.path.join(os.path.dirname(__file__), '../../../state/institution.json')
    with open(os.path.abspath(institution_path), 'r') as f:
        institution = json.load(f)
    rule_types = institution.get('rule_types', {})
    assert 'cap_rule' in rule_types, "cap_rule not registered in institution.rule_types"
    assert 'violation_rule' in rule_types, "violation_rule not registered in institution.rule_types"

def test_communal_reserve_object_exists():
    objects_path = os.path.join(os.path.dirname(__file__), '../../../state/objects.json')
    with open(os.path.abspath(objects_path), 'r') as f:
        objects = json.load(f)
    assert any(o.get('id') == 'communal_reserve' and o.get('type') == 'communal_reserve' for o in objects), "communal_reserve object missing"
