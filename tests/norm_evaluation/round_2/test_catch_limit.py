"""
Test R1, R2: 8% per-trip catch limit verification

R1: harvested_kg(agent, trip) <= 0.08 * stock_before for every fisher on every trip
R2: Excess catch above the 8% limit is not kept
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import pytest
from unittest.mock import patch, MagicMock


def test_catch_limit_configured_to_8_percent():
    """Verify that catch_limit is configured with limit_pct_of_stock = 0.08"""
    import json
    
    with open('state/config.json') as f:
        config = json.load(f)
    
    norms = config.get('norms', [])
    catch_limit_norms = [n for n in norms if n.get('type') == 'catch_limit']
    
    assert len(catch_limit_norms) > 0, "No catch_limit norm found in config"
    
    catch_limit = catch_limit_norms[0]
    assert 'limit_pct_of_stock' in catch_limit, \
        "catch_limit should use limit_pct_of_stock, not limit_kg"
    assert catch_limit['limit_pct_of_stock'] == 0.08, \
        f"catch_limit should be 0.08 (8%), got {catch_limit['limit_pct_of_stock']}"


def test_catch_limit_enforces_8_percent_cap():
    """Verify that catch_limit plugin enforces 8% of stock as the limit"""
    from norms.catch_limit import CatchLimitNorm
    from engine.norms.base import HarvestContext
    
    # Create a mock context with known stock
    context = MagicMock(spec=HarvestContext)
    context.stock_before = 200.0  # 200kg stock
    
    # Create the norm with 8% limit
    norm = CatchLimitNorm({'type': 'catch_limit', 'limit_pct_of_stock': 0.08})
    
    # Calculate expected limit: 8% of 200 = 16kg
    expected_limit = 0.08 * 200.0  # 16kg
    
    # Test that describe reports the correct limit
    description = norm.describe(context, 'agent_1')
    assert description is not None, "Should provide description"
    assert '16' in description or 'limit' in description, \
        f"Should mention the 16kg limit, got: {description}"
    
    # Test enforcement: proposed catch above 8% should be capped
    result = norm.evaluate(context, 'agent_1', raw_kg=20.0, proposed_kg=20.0)
    assert result.kept_kg <= expected_limit + 0.01, \
        f"Should cap at ~16kg (8% of 200), got {result.kept_kg}"
    
    # Test that excess is marked as violation with correct sanction
    if result.kept_kg < 20.0:
        assert result.sanction == 'over_cap', \
            f"Should sanction with 'over_cap', got {result.sanction}"


def test_catch_limit_allows_catch_below_8_percent():
    """Verify that catches below 8% are allowed"""
    from norms.catch_limit import CatchLimitNorm
    from engine.norms.base import HarvestContext
    
    context = MagicMock(spec=HarvestContext)
    context.stock_before = 200.0
    
    norm = CatchLimitNorm({'type': 'catch_limit', 'limit_pct_of_stock': 0.08})
    
    # Proposed catch of 10kg is below 16kg (8% of 200)
    result = norm.evaluate(context, 'agent_1', raw_kg=10.0, proposed_kg=10.0)
    
    assert result.kept_kg == 10.0, \
        f"Should allow full 10kg catch, got {result.kept_kg}"
    assert result.sanction is None, \
        f"Should not sanction when under limit, got {result.sanction}"


def test_excess_catch_not_added_to_payoff():
    """
    Verify R2: Excess catch above 8% is not kept (and therefore doesn't add to payoff).
    The enforcement happens via the kept_kg returned by the norm.
    """
    from norms.catch_limit import CatchLimitNorm
    from engine.norms.base import HarvestContext
    
    context = MagicMock(spec=HarvestContext)
    context.stock_before = 200.0
    
    norm = CatchLimitNorm({'type': 'catch_limit', 'limit_pct_of_stock': 0.08})
    
    # Try to catch 25kg when limit is 16kg
    result = norm.evaluate(context, 'agent_1', raw_kg=25.0, proposed_kg=25.0)
    
    # Should only keep 16kg (the limit)
    assert result.kept_kg <= 16.0, \
        f"Excess should not be kept. Expected max 16kg, got {result.kept_kg}"
    
    # The sanction should indicate over_cap
    assert result.sanction == 'over_cap', \
        f"Should mark as 'over_cap' violation, got {result.sanction}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
