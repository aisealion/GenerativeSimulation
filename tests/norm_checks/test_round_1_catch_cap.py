"""
Round 1 Norm Tests: 10% Catch Cap with 1kg Sustenance Floor

Tests the catch_cap_10pct norm plugin implementing the Round 1 adopted norm:
- Each fisher may take no more than 10% of the lake's current total weight per trip
- Must keep at least 1 kg for sustenance
"""

import pytest

from engine.norms.base import NormDecision
from norms.catch_cap_10pct import CatchCap10PctNorm


class TestCatchCap10PctNorm:
    """Unit tests for the CatchCap10PctNorm plugin."""

    def test_type_name(self):
        """Norm type must be correctly registered."""
        assert CatchCap10PctNorm.type_name == "catch_cap_10pct"

    def test_normal_stock_allows_10_percent(self):
        """With 300kg stock, cap is 30kg."""
        norm = CatchCap10PctNorm(key="test", params={})

        # Create a mock context
        class MockContext:
            stock_before = 300.0

        context = MockContext()

        # Try to catch 25kg (under 30kg limit) - should allow
        decision = norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)
        assert decision.kept_kg == pytest.approx(25.0)
        assert not decision.violated
        assert decision.note is None

    def test_excess_catch_trimmed_to_10_percent(self):
        """With 300kg stock, catching 50kg should be trimmed to 30kg."""
        norm = CatchCap10PctNorm(key="test", params={})

        class MockContext:
            stock_before = 300.0

        context = MockContext()

        # Try to catch 50kg (over 30kg limit) - should trim
        decision = norm.evaluate(context, "agent_0", raw_kg=50.0, proposed_kg=50.0)
        assert decision.kept_kg == pytest.approx(30.0)  # 10% of 300
        assert decision.violated
        assert decision.sanction == "over_10pct_cap"
        assert "30.0kg" in decision.note
        assert "20.0kg was returned" in decision.note

    def test_low_stock_floor_applies(self):
        """With 5kg stock, 10% is 0.5kg but floor is 1kg."""
        norm = CatchCap10PctNorm(key="test", params={})

        class MockContext:
            stock_before = 5.0

        context = MockContext()

        # Try to catch 2kg - should be trimmed to 1kg (floor, not 10%)
        decision = norm.evaluate(context, "agent_0", raw_kg=2.0, proposed_kg=2.0)
        assert decision.kept_kg == pytest.approx(1.0)  # floor applies
        assert decision.violated
        assert "sustenance minimum" in decision.note

    def test_low_stock_allows_floor_amount(self):
        """With 5kg stock, catching exactly 1kg is allowed."""
        norm = CatchCap10PctNorm(key="test", params={})

        class MockContext:
            stock_before = 5.0

        context = MockContext()

        # Catch exactly 1kg - should allow
        decision = norm.evaluate(context, "agent_0", raw_kg=1.0, proposed_kg=1.0)
        assert decision.kept_kg == pytest.approx(1.0)
        assert not decision.violated

    def test_100kg_stock(self):
        """With 100kg stock, cap is 10kg."""
        norm = CatchCap10PctNorm(key="test", params={})

        class MockContext:
            stock_before = 100.0

        context = MockContext()

        # Catch 15kg - should be trimmed to 10kg
        decision = norm.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=15.0)
        assert decision.kept_kg == pytest.approx(10.0)
        assert decision.violated

    def test_describe_shows_limit(self):
        """describe() should return a helpful constraint message."""
        norm = CatchCap10PctNorm(key="test", params={})

        class MockContext:
            stock_before = 300.0

        context = MockContext()

        description = norm.describe(context, "agent_0")
        assert "300kg" in description
        assert "30.0kg" in description
        assert "10%" in description

    def test_describe_shows_floor_when_applicable(self):
        """describe() should mention sustenance floor when 10% < 1kg."""
        norm = CatchCap10PctNorm(key="test", params={})

        class MockContext:
            stock_before = 5.0

        context = MockContext()

        description = norm.describe(context, "agent_0")
        assert "5kg" in description
        assert "minimum sustenance" in description


class TestCatchCapIntegration:
    """Integration tests with the norm registry and harvest action."""

    def test_norm_is_registered(self):
        """The norm type should be auto-discovered by the registry."""
        from engine.norms.registry import NORM_TYPES

        assert "catch_cap_10pct" in NORM_TYPES
        assert NORM_TYPES["catch_cap_10pct"] is CatchCap10PctNorm

    def test_norm_loads_from_config(self):
        """Registry should load the norm from config."""
        from engine.norms.registry import load_norms

        config = {"norms": [{"type": "catch_cap_10pct", "id": "test_cap"}]}
        norms = load_norms(config)

        assert len(norms) == 1
        assert isinstance(norms[0], CatchCap10PctNorm)
        assert norms[0].key == "test_cap"
