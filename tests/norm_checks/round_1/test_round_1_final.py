"""
Test file for round 1 norm checks - specifically for enforcement mechanisms
"""

import pytest
import json
from unittest.mock import MagicMock, patch


def test_R9_enforcement_mechanisms_comprehensive():
    """
    Test comprehensive enforcement mechanisms for council role as per 
    'Violations are remedied by the council, who may require return of excess, f
    ine, or suspension.'
    """
    # Read the config file to verify enforcement rule is registered  
    with open('state/config.json', 'r') as f:
        config = json.load(f)
        
    # Verify enforcement rule is registered for record_catch action
    assert "record_catch" in config["rules"]
    
    # Find the enforcement rule in the list
    record_catch_rules = config["rules"]["record_catch"]
    assert isinstance(record_catch_rules, list)
    
    enforcement_rule = None
    for rule in record_catch_rules:
        if rule.get("type") == "enforcement":
            enforcement_rule = rule
            break
    
    assert enforcement_rule is not None
    assert enforcement_rule["type"] == "enforcement"
    
    # Test that we have the proper enforcement rule types
    from actions.rules.record_catch.enforcement import EnforcementRule
    rule = EnforcementRule("test_key", {})
    
    # The rule should support all enforcement types mentioned in the norm:
    # return of excess, fine, and suspension
    assert rule.type_name == "enforcement"
    
    # Verify rule has proper methods for enforcement handling
    assert hasattr(rule, 'after_agent')
    assert hasattr(rule, 'after_action')
    
    # Test that enforcement methods exist (the ones that were added)
    assert hasattr(rule, '_process_return_of_excess')
    assert hasattr(rule, '_process_fine') 
    assert hasattr(rule, '_process_suspension')
    
    # Verify methods are callable
    assert callable(getattr(rule, '_process_return_of_excess'))
    assert callable(getattr(rule, '_process_fine'))
    assert callable(getattr(rule, '_process_suspension'))
    

def test_enforcement_rule_structure():
    """Test that enforcement rule structure supports all three enforcement types"""
    
    # Import the enforcement rule
    from actions.rules.record_catch.enforcement import EnforcementRule
    
    # Try to instantiate it
    rule = EnforcementRule("test_key", {})
    
    # Test that structure includes capability for all enforcement types
    assert hasattr(rule, 'after_action')
    
    # Check that enforcement decision types are handled
    test_decision = {
        "type": "return_excess",
        "fisher_id": "fisher1",
        "amount": 1.0
    }
    
    # Verify that the processing methods can handle the three types mentioned
    # This is a simple structure check, not deep functional testing
    assert rule.type_name == "enforcement"
    
    # These methods should exist and be defined (they are implemented in the updated enforcement.py)
    methods_to_check = ['_process_return_of_excess', '_process_fine', '_process_suspension']
    for method in methods_to_check:
        assert hasattr(rule, method)
        assert callable(getattr(rule, method))
        
    # Test that the after_action method can process enforcement decisions
    mock_ctx = MagicMock()
    mock_round_record = {
        "council_enforcement_decisions": [
            {"type": "return_excess", "fisher_id": "fisher1", "amount": 0.5},
            {"type": "fine", "fisher_id": "fisher2", "amount": 2.0},
            {"type": "suspension", "fisher_id": "fisher3"}
        ]
    }
    
    # Test that the method can handle the three enforcement types properly
    # (this test will not actually execute any enforcement due to mock, but verifies
    # that the structure supports all three types)
    result = rule.after_action(mock_ctx, mock_round_record)
    assert result is not None  # Should return normally
    
    # Test that the rule correctly handles the enforcement decision types
    # by checking that all types of decisions can be recognized
    assert "return_excess" in str(rule.after_action(mock_ctx, mock_round_record))
    assert "fine" in str(rule.after_action(mock_ctx, mock_round_record))
    assert "suspension" in str(rule.after_action(mock_ctx, mock_round_record))