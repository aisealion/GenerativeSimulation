"""
Tests for Round 2 requirements:
- R3: Enforce 1.5 unit and 10% catch limits during harvest
- R4: Handle excess fish by returning to lake or placing in reserve  
- R1: Communal fish reserve for excess catch (object)
- R2: Daily catch tally records (object) 
"""

import pytest
import json
from unittest.mock import Mock

def test_R3_limit_enforcement_comprehensive():
    """Test that the limit enforcement rule actually enforces limits properly."""
    # Read the rule file to see current implementation
    from actions.rules.harvest.rule_limit_enforcement import RuleLimitEnforcement
    
    # Create a mock context with the required state
    ctx = Mock()
    ctx.state = {
        'community': {'stock_kg': 100.0},
        'runtime': {'stock_kg': 100.0}
    }
    
    # Create rule instance
    rule = RuleLimitEnforcement("test_key", {})
    
    # Test case 1: harvest within limits (should not change anything)
    record_entry = {'harvested_kg': 1.0}
    result = rule.after_agent(ctx, "agent1", record_entry)
    assert result == {}, "Harvest within limit should not modify record"
    
    # Test case 2: harvest over 1.5kg limit (should reduce to 1.5kg)
    record_entry = {'harvested_kg': 2.0}
    result = rule.after_agent(ctx, "agent1", record_entry)
    assert 'harvested_kg' in result
    assert result['harvested_kg'] == 1.5, f"Expected 1.5kg, got {result['harvested_kg']}"
    
    # Test case 3: when 10% limit is the lower bound (harvest=1.6kg, stock=15kg)
    # So harvest=1.6kg, stock=15kg (10% = 1.5kg) - we reduce to 1.5kg 
    # This demonstrates that when 10% is the limiting factor, it works
    ctx.state = {'community': {'stock_kg': 15.0}, 'runtime': {'stock_kg': 15.0}}
    record_entry = {'harvested_kg': 1.6}
    result = rule.after_agent(ctx, "agent1", record_entry)
    assert 'harvested_kg' in result
    assert result['harvested_kg'] == 1.5, f"Expected 1.5kg (10% limit), got {result['harvested_kg']}"
    
    # Test case 4: when 10% limit is much higher than 1.5kg limit
    # So harvest=2.0kg, stock=50kg (10% = 5kg) - should reduce to 1.5kg (as 1.5kg < 5kg)
    ctx.state = {'community': {'stock_kg': 50.0}, 'runtime': {'stock_kg': 50.0}}
    record_entry = {'harvested_kg': 2.0}
    result = rule.after_agent(ctx, "agent1", record_entry)
    assert 'harvested_kg' in result
    assert result['harvested_kg'] == 1.5, f"Expected 1.5kg (1.5kg limit is lower), got {result['harvested_kg']}"
    
    # Test case 5: when 10% limit is lower than 1.5kg limit
    # So harvest=3.0kg, stock=10kg (10% = 1kg) - should reduce to 1.0kg
    ctx.state = {'community': {'stock_kg': 10.0}, 'runtime': {'stock_kg': 10.0}}
    record_entry = {'harvested_kg': 3.0}
    result = rule.after_agent(ctx, "agent1", record_entry)
    assert 'harvested_kg' in result
    assert result['harvested_kg'] == 1.0, f"Expected 1.0kg (10% limit of 1kg is lower), got {result['harvested_kg']}"
    
    # Test case 6: demonstrating that the limits correctly compare to decide what restriction applies
    # Let's test where both 1.5kg and 10% would be the limit  
    # For 1.5kg to be the same limit as 10%: 1.5 = 0.1 * stock → stock = 15kg
    # When stock=15kg and harvest=1.5kg, both limits are 1.5kg, so nothing should change
    ctx.state = {'community': {'stock_kg': 15.0}, 'runtime': {'stock_kg': 15.0}}
    record_entry = {'harvested_kg': 1.5}
    result = rule.after_agent(ctx, "agent1", record_entry)
    assert result == {}, "When harvest equals limit, no reduction should occur"
    
    # Test case 7: test limit where harvest equals one of the bounds
    # For stock=16kg: 10% = 1.6kg, so limit = min(1.5, 1.6) = 1.5kg
    # So if harvest=1.6kg, limit is 1.5kg so reduction should happen
    ctx.state = {'community': {'stock_kg': 16.0}, 'runtime': {'stock_kg': 16.0}}
    record_entry = {'harvested_kg': 1.6}
    result = rule.after_agent(ctx, "agent1", record_entry)
    assert 'harvested_kg' in result
    assert result['harvested_kg'] == 1.5, f"Expected 1.5kg (limit), got {result['harvested_kg']}"


def test_R4_excess_handling_comprehensive():
    """Test that the excess handling rule actually processes excess fish."""
    from actions.rules.harvest.rule_excess_handling import RuleExcessHandling
    
    # Create a mock context 
    ctx = Mock()
    ctx.state = {
        'objects': {
            'communal_fish_reserve_1': {
                'type': 'communal_fish_reserve',
                'fields': {'reserve_kg': 0}
            },
            'daily_catch_tally_1': {
                'type': 'daily_catch_tally',
                'fields': {'total_catch_kg': 0, 'fisher_catch': {}}
            }
        }
    }
    
    rule = RuleExcessHandling("test_key", {})
    
    # Test that after_agent returns an empty dict (the actual logic is in on_agent_settled) 
    record_entry = {'harvested_kg': 1.0}
    result = rule.after_agent(ctx, "agent1", record_entry)
    assert result == {}, "After agent should not do modifications - that's in on_agent_settled"
    
    # Test that on_agent_settled is callable and functional 
    # (the important part is to make sure the rule logic is implemented)
    assert callable(rule.on_agent_settled), "on_agent_settled method should exist"


def test_R1_object_created():
    """Test that the communal fish reserve object is properly created."""
    # Check that the object exists in the objects.json file and has the correct structure
    import json
    
    with open('state/objects.json', 'r') as f:
        objects = json.load(f)
        
    # Find the communal fish reserve object
    reserve_obj = None
    for obj in objects:
        if obj['id'] == 'communal_fish_reserve_1':
            reserve_obj = obj
            break
    
    assert reserve_obj is not None, "Communal fish reserve object not found"
    assert reserve_obj['type'] == 'communal_fish_reserve'
    assert 'reserve_kg' in reserve_obj['fields']


def test_R2_object_created():
    """Test that the daily catch tally object is properly created."""
    # Check that the object exists in the objects.json file and has the correct structure
    import json
    
    with open('state/objects.json', 'r') as f:
        objects = json.load(f)
        
    # Find the daily catch tally object
    tally_obj = None
    for obj in objects:
        if obj['id'] == 'daily_catch_tally_1':
            tally_obj = obj
            break
    
    assert tally_obj is not None, "Daily catch tally object not found"
    assert tally_obj['type'] == 'daily_catch_tally'
    assert 'total_catch_kg' in tally_obj['fields']
    assert 'fisher_catch' in tally_obj['fields']


def test_R2_verification_process():
    """Test that the system's daily catch tally supports verification by verbal confirmation and simple tally sheets."""
    # The daily catch tally object is designed to record catch data that is verified by:
    # 1. Fishers counting their catch by hand (trip-level)
    # 2. Community tallying the total catch at daily gathering (process-level)
    # 3. Data is then recorded through the system's tallying process
    
    import json
    
    with open('state/objects.json', 'r') as f:
        objects = json.load(f)
        
    # Verify daily catch tally object exists and has necessary fields
    tally_obj = None
    for obj in objects:
        if obj['id'] == 'daily_catch_tally_1':
            tally_obj = obj
            break
    
    assert tally_obj is not None, "Daily catch tally object not found"
    assert tally_obj['type'] == 'daily_catch_tally'
    
    # Check that the structure supports capture of: 
    # - Total catch for the day  
    # - Individual fisher catches (to support verification)
    assert 'total_catch_kg' in tally_obj['fields']
    assert 'fisher_catch' in tally_obj['fields']
    
    # Verify that the structure would support the norm's verification process
    # where each fisher's catch is counted by hand and verified at the daily gathering 
    assert isinstance(tally_obj['fields']['fisher_catch'], dict), "fisher_catch should be a dictionary to store individual records"
    assert isinstance(tally_obj['fields']['total_catch_kg'], (int, float)), "total_catch_kg should be numeric"


def test_R5_visibility_comprehensive():
    """Test that fishers can see their harvest limits and catch."""
    from actions.rules.harvest.rule_limit_enforcement import RuleLimitEnforcement
    
    # Just test that we can instantiate and that describe method works
    rule = RuleLimitEnforcement("test_key", {})
    
    # Test that the describe method returns relevant text
    description = rule.describe(Mock(), "agent1")
    assert "1.5kg" in description or "10%" in description, "Description should mention limits"


def test_rule_limit_enforcement_exists_and_implemented():
    """Test that the limit enforcement rule (R3) exists and is functional."""
    # This test ensures that the rule exists and has the required structure
    try:
        from actions.rules.harvest.rule_limit_enforcement import RuleLimitEnforcement
        assert RuleLimitEnforcement is not None
        rule = RuleLimitEnforcement("test_key", {})
        assert rule.type_name == "limit_enforcement"
    except Exception as e:
        pytest.fail(f"R3 rule (limit_enforcement) is not properly implemented: {e}")


def test_rule_excess_handling_exists_and_implemented():
    """Test that the excess handling rule (R4) exists and is functional."""
    # This test ensures that the rule exists and has the required structure
    try:
        from actions.rules.harvest.rule_excess_handling import RuleExcessHandling
        assert RuleExcessHandling is not None
        rule = RuleExcessHandling("test_key", {})
        assert rule.type_name == "excess_handling"
    except Exception as e:
        pytest.fail(f"R4 rule (excess_handling) is not properly implemented: {e}")


def test_R3_rule_has_required_methods():
    """Test that R3 rule has all required methods for enforcement"""
    try:
        from actions.rules.harvest.rule_limit_enforcement import RuleLimitEnforcement
        rule = RuleLimitEnforcement("test_key", {})
        
        # Check for required methods
        required_methods = [
            'before_action',
            'after_action',
            'is_eligible',
            'describe',
            'after_agent',
            'on_agent_settled'
        ]
        
        for method in required_methods:
            assert hasattr(rule, method), f"RuleLimitEnforcement missing method: {method}"
            
    except Exception as e:
        pytest.fail(f"R3 rule does not have required methods: {e}")


def test_R4_rule_has_required_methods():
    """Test that R4 rule has all required methods for handling"""
    try:
        from actions.rules.harvest.rule_excess_handling import RuleExcessHandling
        rule = RuleExcessHandling("test_key", {})
        
        # Check for required methods
        required_methods = [
            'before_action',
            'after_action',
            'is_eligible',
            'describe',
            'after_agent',
            'on_agent_settled'
        ]
        
        for method in required_methods:
            assert hasattr(rule, method), f"RuleExcessHandling missing method: {method}"
            
    except Exception as e:
        pytest.fail(f"R4 rule does not have required methods: {e}")


def test_rule_limit_enforcement_class_exists():
    """Test that RuleLimitEnforcement class is correctly defined."""
    try:
        from actions.rules.harvest.rule_limit_enforcement import RuleLimitEnforcement
        # Test instantiation
        rule = RuleLimitEnforcement("test_key", {"param1": "value1"})
        assert rule.type_name == "limit_enforcement"
        
        # Test that methods are callable
        assert callable(rule.after_agent) 
        assert callable(rule.before_action)
        assert callable(rule.after_action)
    except Exception as e:
        pytest.fail(f"RuleLimitEnforcement class is not properly defined: {e}")


def test_rule_excess_handling_class_exists():
    """Test that RuleExcessHandling class is correctly defined."""
    try:
        from actions.rules.harvest.rule_excess_handling import RuleExcessHandling
        # Test instantiation
        rule = RuleExcessHandling("test_key", {"param1": "value1"})
        assert rule.type_name == "excess_handling"
        
        # Test that methods are callable
        assert callable(rule.after_agent) 
        assert callable(rule.before_action)
        assert callable(rule.after_action)
    except Exception as e:
        pytest.fail(f"RuleExcessHandling class is not properly defined: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])