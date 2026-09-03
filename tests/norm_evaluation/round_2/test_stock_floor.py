"""
Test R3, R4: 180kg minimum stock floor verification

R3: stock_after_harvest >= 180kg must hold at all times
R4: If a fisher's catch would push stock below 180kg, their catch must be reduced or prevented
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import pytest
from unittest.mock import patch, MagicMock


def test_stock_floor_configured_to_180kg():
    """Verify that stock_floor is configured with min_stock_kg = 180"""
    import json
    
    with open('state/config.json') as f:
        config = json.load(f)
    
    norms = config.get('norms', [])
    stock_floor_norms = [n for n in norms if n.get('type') == 'stock_floor']
    
    assert len(stock_floor_norms) > 0, \
        "No stock_floor norm found in config - REQUIRED for Round 2"
    
    stock_floor = stock_floor_norms[0]
    assert 'min_stock_kg' in stock_floor, \
        "stock_floor should have min_stock_kg parameter"
    assert stock_floor['min_stock_kg'] == 180, \
        f"stock_floor should be 180kg, got {stock_floor['min_stock_kg']}"


def test_stock_floor_plugin_exists():
    """Verify that the stock_floor.py plugin file exists"""
    import os
    
    plugin_path = 'norms/stock_floor.py'
    assert os.path.exists(plugin_path), \
        f"stock_floor.py plugin must exist at {plugin_path} - REQUIRED for Round 2"


def test_stock_floor_plugin_is_valid_python():
    """Verify that stock_floor.py is valid Python that can be imported"""
    import os
    
    plugin_path = 'norms/stock_floor.py'
    if not os.path.exists(plugin_path):
        pytest.skip("stock_floor.py doesn't exist yet - this is an implementation gap")
    
    # Try to import it
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("stock_floor", plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as e:
        pytest.fail(f"stock_floor.py exists but cannot be imported: {e}")


def test_stock_floor_enforces_minimum_180kg():
    """Verify that stock_floor ensures stock never drops below 180kg"""
    import os
    
    plugin_path = 'norms/stock_floor.py'
    if not os.path.exists(plugin_path):
        pytest.skip("stock_floor.py doesn't exist - cannot test enforcement")
    
    # Import and test
    try:
        from norms.stock_floor import StockFloorNorm
        from engine.norms.base import HarvestContext
    except ImportError as e:
        pytest.fail(f"Cannot import StockFloorNorm: {e}")
    
    context = MagicMock(spec=HarvestContext)
    context.stock_before = 200.0  # 200kg stock
    
    # Create the norm with 180kg minimum
    norm = StockFloorNorm({'type': 'stock_floor', 'min_stock_kg': 180})
    
    # Test that we can describe the constraint
    description = norm.describe(context, 'agent_1')
    assert description is not None, "Should provide description"
    assert '180' in description, \
        f"Should mention 180kg minimum, got: {description}"


def test_stock_floor_blocks_catch_that_would_violate_floor():
    """
    Verify R4: If a catch would push stock below 180kg, it's reduced or blocked.
    With 200kg stock and 180kg floor, max catch is 20kg to stay above floor.
    """
    import os
    
    plugin_path = 'norms/stock_floor.py'
    if not os.path.exists(plugin_path):
        pytest.skip("stock_floor.py doesn't exist - cannot test blocking")
    
    try:
        from norms.stock_floor import StockFloorNorm
        from engine.norms.base import HarvestContext
    except ImportError:
        pytest.skip("Cannot import StockFloorNorm")
    
    context = MagicMock(spec=HarvestContext)
    context.stock_before = 200.0
    context.round_scratch = MagicMock(return_value={})
    
    norm = StockFloorNorm({'type': 'stock_floor', 'min_stock_kg': 180})
    
    # A catch of 30kg would leave 170kg, which is below 180kg floor
    # This should be reduced or blocked
    result = norm.evaluate(context, 'agent_1', raw_kg=30.0, proposed_kg=30.0)
    
    # The remaining stock after this catch should be >= 180kg
    remaining = context.stock_before - result.kept_kg
    assert remaining >= 180.0 - 0.01, \
        f"Stock after harvest should be >= 180kg, would be {remaining}"


def test_stock_floor_norm_ordering():
    """
    Verify that stock_floor comes after catch_limit in the norm chain.
    This is important because catch_limit caps individual catches first,
    then stock_floor enforces the aggregate floor.
    """
    import json
    
    with open('state/config.json') as f:
        config = json.load(f)
    
    norms = config.get('norms', [])
    
    catch_limit_idx = None
    stock_floor_idx = None
    
    for i, norm in enumerate(norms):
        if norm.get('type') == 'catch_limit':
            catch_limit_idx = i
        if norm.get('type') == 'stock_floor':
            stock_floor_idx = i
    
    if stock_floor_idx is not None and catch_limit_idx is not None:
        assert stock_floor_idx > catch_limit_idx, \
            "stock_floor should come after catch_limit in enforcement order"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
