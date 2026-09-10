"""
Independent evaluation tests for Round 1 Norm Implementation.

These tests verify compliance with the requirements from state/norm_specs/round_1.md
without relying on the norm-implementer's own test suite.
"""

import pytest

from engine.norms.base import NormDecision
from engine.norms.registry import load_norms, NORM_TYPES
from norms.catch_cap_10pct import CatchCap10PctNorm


class MockContext:
    """Simple mock context for testing."""
    def __init__(self, stock_before):
        self.stock_before = stock_before


class TestR1PerTripCatchCap:
    """R1: Per-Trip Catch Cap (10% of Stock)
    
    Requirement: Each fisher's catch per trip is capped at 10% of the lake's 
    current total weight (stock_before).
    """

    def test_stock_300kg_cap_is_30kg(self):
        """Verification Criteria 1: When stock is 300 kg, cap is 30 kg per fisher per trip"""
        norm = CatchCap10PctNorm(key="test", params={})
        context = MockContext(stock_before=300.0)
        
        # Catch exactly 30kg - should be allowed
        decision = norm.evaluate(context, "agent_0", raw_kg=30.0, proposed_kg=30.0)
        assert decision.kept_kg == pytest.approx(30.0), "30kg should be allowed (10% of 300kg)"
        assert not decision.violated, "Should not be a violation at exactly 10%"
        
        # Catch 31kg - should be trimmed to 30kg
        decision = norm.evaluate(context, "agent_0", raw_kg=31.0, proposed_kg=31.0)
        assert decision.kept_kg == pytest.approx(30.0), "31kg should be trimmed to 30kg"
        assert decision.violated, "Should be a violation when exceeding 10%"

    def test_stock_100kg_cap_is_10kg(self):
        """Verification Criteria 3: When stock is 100 kg, cap is 10 kg"""
        norm = CatchCap10PctNorm(key="test", params={})
        context = MockContext(stock_before=100.0)
        
        # Catch exactly 10kg - should be allowed
        decision = norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
        assert decision.kept_kg == pytest.approx(10.0), "10kg should be allowed (10% of 100kg)"
        assert not decision.violated
        
        # Catch 15kg - should be trimmed to 10kg
        decision = norm.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=15.0)
        assert decision.kept_kg == pytest.approx(10.0), "15kg should be trimmed to 10kg"
        assert decision.violated

    def test_excess_catch_is_trimmed(self):
        """Verification Criteria 4: Excess catch is trimmed and recorded as violation"""
        norm = CatchCap10PctNorm(key="test", params={})
        context = MockContext(stock_before=200.0)
        
        # 10% of 200kg = 20kg
        # Catch 50kg - should be trimmed to 20kg
        decision = norm.evaluate(context, "agent_0", raw_kg=50.0, proposed_kg=50.0)
        assert decision.kept_kg == pytest.approx(20.0), "50kg should be trimmed to 20kg"
        assert decision.violated, "Should be a violation"
        assert decision.sanction is not None, "Should have a sanction"

    def test_violation_note_includes_excess_amount(self):
        """Verification Criteria 5: Violation note includes the amount of excess returned"""
        norm = CatchCap10PctNorm(key="test", params={})
        context = MockContext(stock_before=200.0)
        
        # 10% of 200kg = 20kg
        # Catch 50kg - excess is 30kg
        decision = norm.evaluate(context, "agent_0", raw_kg=50.0, proposed_kg=50.0)
        assert decision.violated
        assert decision.note is not None, "Should have a note"
        # Note should mention the amount returned (30kg)
        assert "30.0" in decision.note or "30" in decision.note, f"Note should mention excess amount: {decision.note}"


class TestR2MinimumSustenanceFloor:
    """R2: Minimum Sustenance Floor (1 kg)
    
    Requirement: Fishers must keep at least 1 kg for sustenance. This means 
    the effective catch is max(10% of stock, 1 kg) when the 10% calculation 
    yields less than 1 kg.
    """

    def test_stock_5kg_floor_is_1kg(self):
        """Verification Criteria 2: When stock is 5 kg, fisher may still keep 1 kg (floor)"""
        norm = CatchCap10PctNorm(key="test", params={})
        context = MockContext(stock_before=5.0)
        
        # 10% of 5kg = 0.5kg, but floor is 1kg
        # So effective limit is 1kg
        
        # Catch 1kg - should be allowed (floor applies)
        decision = norm.evaluate(context, "agent_0", raw_kg=1.0, proposed_kg=1.0)
        assert decision.kept_kg == pytest.approx(1.0), "1kg should be allowed (floor)"
        assert not decision.violated, "Should not be a violation at floor amount"

    def test_stock_5kg_catch_above_floor_trimmed(self):
        """When stock is 5kg, catching above 1kg should be trimmed to 1kg"""
        norm = CatchCap10PctNorm(key="test", params={})
        context = MockContext(stock_before=5.0)
        
        # Catch 2kg - should be trimmed to 1kg (floor)
        decision = norm.evaluate(context, "agent_0", raw_kg=2.0, proposed_kg=2.0)
        assert decision.kept_kg == pytest.approx(1.0), "2kg should be trimmed to 1kg (floor)"
        assert decision.violated, "Should be a violation when exceeding floor"

    def test_very_low_stock_floor_applies(self):
        """With very low stock (1kg), floor still ensures 1kg can be kept"""
        norm = CatchCap10PctNorm(key="test", params={})
        context = MockContext(stock_before=1.0)
        
        # 10% of 1kg = 0.1kg, but floor is 1kg
        # So effective limit is 1kg
        
        # Catch 1kg - should be allowed
        decision = norm.evaluate(context, "agent_0", raw_kg=1.0, proposed_kg=1.0)
        assert decision.kept_kg == pytest.approx(1.0), "1kg should be allowed even with 1kg stock"


class TestImplementationDetails:
    """Test implementation-specific details from the spec."""

    def test_formula_kept_kg_is_min_of_raw_and_max_cap_floor(self):
        """Verify the formula: kept_kg = min(raw_kg, max(limit_kg, 1.0))"""
        norm = CatchCap10PctNorm(key="test", params={})
        
        # Test case 1: Normal stock, under cap
        # stock=300, cap=30, raw=25 -> kept=25
        context = MockContext(stock_before=300.0)
        decision = norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)
        assert decision.kept_kg == pytest.approx(25.0)
        
        # Test case 2: Normal stock, over cap
        # stock=300, cap=30, raw=50 -> kept=30
        decision = norm.evaluate(context, "agent_0", raw_kg=50.0, proposed_kg=50.0)
        assert decision.kept_kg == pytest.approx(30.0)
        
        # Test case 3: Low stock, floor applies
        # stock=5, cap=0.5, floor=1, raw=2 -> kept=1
        context = MockContext(stock_before=5.0)
        decision = norm.evaluate(context, "agent_0", raw_kg=2.0, proposed_kg=2.0)
        assert decision.kept_kg == pytest.approx(1.0)

    def test_sanction_is_over_10pct_cap(self):
        """Verify that violation sanction is properly labeled"""
        norm = CatchCap10PctNorm(key="test", params={})
        context = MockContext(stock_before=300.0)
        
        decision = norm.evaluate(context, "agent_0", raw_kg=50.0, proposed_kg=50.0)
        assert decision.violated
        assert decision.sanction == "over_10pct_cap", f"Expected sanction 'over_10pct_cap', got {decision.sanction}"


class TestConfigAndRegistry:
    """Test that the norm integrates properly with the config system."""

    def test_norm_type_registered(self):
        """The norm type should be discoverable by the registry"""
        assert "catch_cap_10pct" in NORM_TYPES
        assert NORM_TYPES["catch_cap_10pct"] is CatchCap10PctNorm

    def test_norm_loads_from_config_with_expected_schema(self):
        """Verify the config schema from the spec works:
        
        {
          "norms": [
            {
              "type": "catch_cap_10pct",
              "id": "round1_cap"
            }
          ]
        }
        """
        config = {
            "norms": [
                {
                    "type": "catch_cap_10pct",
                    "id": "round1_cap"
                }
            ]
        }
        norms = load_norms(config)
        
        assert len(norms) == 1
        assert isinstance(norms[0], CatchCap10PctNorm)
        assert norms[0].key == "round1_cap"

    def test_state_config_has_expected_norm(self):
        """Verify state/config.json has the expected norm configuration"""
        import json
        
        with open("state/config.json") as f:
            config = json.load(f)
        
        assert "norms" in config
        norms = config["norms"]
        assert len(norms) >= 1
        
        # Find the catch_cap_10pct norm
        catch_cap_norms = [n for n in norms if n.get("type") == "catch_cap_10pct"]
        assert len(catch_cap_norms) >= 1, "Should have at least one catch_cap_10pct norm"


class TestDescribeMethod:
    """Test the describe() method that informs agents of their constraints."""

    def test_describe_normal_stock(self):
        """describe() should show the 10% cap for normal stock levels"""
        norm = CatchCap10PctNorm(key="test", params={})
        context = MockContext(stock_before=300.0)
        
        description = norm.describe(context, "agent_0")
        assert description is not None
        # Should mention stock and cap
        assert "300" in description, f"Should mention stock amount: {description}"
        assert "30" in description, f"Should mention cap amount: {description}"

    def test_describe_low_stock(self):
        """describe() should mention sustenance floor when cap < 1kg"""
        norm = CatchCap10PctNorm(key="test", params={})
        context = MockContext(stock_before=5.0)
        
        description = norm.describe(context, "agent_0")
        assert description is not None
        # When stock is 5kg, 10% = 0.5kg, but floor is 1kg
        # Should mention the floor/sustenance minimum
        assert "1" in description, f"Should mention floor amount: {description}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
