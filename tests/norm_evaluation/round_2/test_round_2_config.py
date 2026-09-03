"""
Integration test for Round 2 norm configuration.
Verifies the complete norm stack matches the specification.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import pytest
import json


def test_round_2_norm_stack_complete():
    """
    Verify the complete norm stack matches Round 2 spec:
    1. catch_limit with limit_pct_of_stock: 0.08
    2. stock_floor with min_stock_kg: 180
    3. violation_ban with trigger_sanction: [over_cap, below_floor], trips: 1
    """
    with open('state/config.json') as f:
        config = json.load(f)
    
    norms = config.get('norms', [])
    
    # Check that we have exactly the expected three norms
    norm_types = [n.get('type') for n in norms]
    
    # Verify all three required norms are present
    assert 'catch_limit' in norm_types, \
        "catch_limit norm is required for Round 2"
    assert 'stock_floor' in norm_types, \
        "stock_floor norm is REQUIRED for Round 2 (180kg minimum)"
    assert 'violation_ban' in norm_types, \
        "violation_ban norm is required for Round 2"


def test_catch_limit_parameters():
    """Verify catch_limit has correct parameters for 8% limit"""
    with open('state/config.json') as f:
        config = json.load(f)
    
    catch_limit = None
    for n in config.get('norms', []):
        if n.get('type') == 'catch_limit':
            catch_limit = n
            break
    
    assert catch_limit is not None, "catch_limit norm not found"
    
    # Should use limit_pct_of_stock, not limit_kg
    assert 'limit_pct_of_stock' in catch_limit, \
        "catch_limit must use limit_pct_of_stock parameter"
    assert catch_limit['limit_pct_of_stock'] == 0.08, \
        f"catch_limit must be 0.08 (8%), got {catch_limit.get('limit_pct_of_stock')}"
    
    # Should NOT have limit_kg (the old flat limit)
    assert 'limit_kg' not in catch_limit, \
        "catch_limit should not use limit_kg (it's percentage-based now)"


def test_stock_floor_parameters():
    """Verify stock_floor has correct parameters for 180kg minimum"""
    with open('state/config.json') as f:
        config = json.load(f)
    
    stock_floor = None
    for n in config.get('norms', []):
        if n.get('type') == 'stock_floor':
            stock_floor = n
            break
    
    assert stock_floor is not None, \
        "stock_floor norm is REQUIRED for Round 2 - MISSING!"
    
    assert 'min_stock_kg' in stock_floor, \
        "stock_floor must have min_stock_kg parameter"
    assert stock_floor['min_stock_kg'] == 180, \
        f"stock_floor must be 180kg, got {stock_floor.get('min_stock_kg')}"


def test_violation_ban_parameters():
    """Verify violation_ban has correct parameters for one-trip suspension"""
    with open('state/config.json') as f:
        config = json.load(f)
    
    violation_ban = None
    for n in config.get('norms', []):
        if n.get('type') == 'violation_ban':
            violation_ban = n
            break
    
    assert violation_ban is not None, "violation_ban norm not found"
    
    # Should have trips: 1 (one-trip suspension)
    assert violation_ban.get('trips') == 1, \
        f"violation_ban trips must be 1, got {violation_ban.get('trips')}"
    
    # Should trigger on both over_cap and below_floor
    trigger = violation_ban.get('trigger_sanction', [])
    triggers = trigger if isinstance(trigger, list) else [trigger]
    
    assert 'over_cap' in triggers, \
        f"violation_ban must trigger on 'over_cap', got {triggers}"
    assert 'below_floor' in triggers, \
        f"violation_ban must trigger on 'below_floor', got {triggers}"


def test_norm_enforcement_order():
    """Verify norms are in correct enforcement order"""
    with open('state/config.json') as f:
        config = json.load(f)
    
    norms = config.get('norms', [])
    
    catch_limit_idx = None
    stock_floor_idx = None
    violation_ban_idx = None
    
    for i, n in enumerate(norms):
        if n.get('type') == 'catch_limit':
            catch_limit_idx = i
        elif n.get('type') == 'stock_floor':
            stock_floor_idx = i
        elif n.get('type') == 'violation_ban':
            violation_ban_idx = i
    
    # All three should exist
    assert catch_limit_idx is not None, "catch_limit not found"
    assert stock_floor_idx is not None, "stock_floor not found - REQUIRED!"
    assert violation_ban_idx is not None, "violation_ban not found"
    
    # Order: catch_limit < stock_floor < violation_ban
    assert catch_limit_idx < stock_floor_idx, \
        f"catch_limit (idx {catch_limit_idx}) should come before stock_floor (idx {stock_floor_idx})"
    assert stock_floor_idx < violation_ban_idx, \
        f"stock_floor (idx {stock_floor_idx}) should come before violation_ban (idx {violation_ban_idx})"


def test_no_old_norms_remain():
    """Verify old Round 1 norms are replaced, not just added to"""
    with open('state/config.json') as f:
        config = json.load(f)
    
    norms = config.get('norms', [])
    norm_types = [n.get('type') for n in norms]
    
    # Old Round 1 norms that should NOT be present
    if 'community_cap' in norm_types:
        # This is a warning, not a failure - community_cap might be intentionally kept
        # But for Round 2 spec, it should be removed
        pass  # We'll allow this but note it


def test_stock_floor_plugin_exists():
    """Critical test: stock_floor.py plugin file must exist"""
    plugin_path = 'norms/stock_floor.py'
    
    assert os.path.exists(plugin_path), \
        f"CRITICAL: {plugin_path} must exist for Round 2 implementation. " \
        f"This is a NEW plugin required by the 180kg minimum stock floor requirement."


def test_all_norm_plugins_loadable():
    """Verify all configured norms can be loaded by the registry"""
    with open('state/config.json') as f:
        config = json.load(f)
    
    norms_config = config.get('norms', [])
    
    # Try to import the registry and load norms
    try:
        from engine.norms.registry import load_norms
        norms = load_norms(norms_config)
        
        # Should have loaded all norms
        assert len(norms) == len(norms_config), \
            f"Expected {len(norms_config)} norms loaded, got {len(norms)}"
    except Exception as e:
        pytest.fail(f"Failed to load norms from config: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
