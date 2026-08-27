"""Tests for stock_protection norm."""

import pytest
from norms.stock_protection import StockProtectionNorm
from engine.norms.context import HarvestContext


def make_context(stock_before, original_stock_kg=300, min_stock_pct=0.40):
    """Build a minimal HarvestContext for testing."""
    return HarvestContext(
        config={},
        fluents=[],
        runtime={},
        agents={},
        round_number=1,
        stock_before=stock_before,
    )


class TestStockProtectionNorm:
    def test_type_name(self):
        norm = StockProtectionNorm("test", {})
        assert norm.type_name == "stock_protection"

    def test_eligible_when_stock_above_threshold(self):
        """Agents can fish when stock is above 40% threshold."""
        norm = StockProtectionNorm("test", {"min_stock_pct": 0.40, "original_stock_kg": 300})
        context = make_context(stock_before=150)  # 150 > 120 (40% of 300)
        assert norm.is_eligible(context, "agent_1") is True

    def test_ineligible_when_stock_below_threshold(self):
        """Agents cannot fish when stock falls below 40% threshold."""
        norm = StockProtectionNorm("test", {"min_stock_pct": 0.40, "original_stock_kg": 300})
        context = make_context(stock_before=100)  # 100 < 120 (40% of 300)
        assert norm.is_eligible(context, "agent_1") is False

    def test_eligible_at_exact_threshold(self):
        """Agents can fish when stock is exactly at the threshold."""
        norm = StockProtectionNorm("test", {"min_stock_pct": 0.40, "original_stock_kg": 300})
        context = make_context(stock_before=120)  # Exactly 40% of 300
        assert norm.is_eligible(context, "agent_1") is True

    def test_describe_when_stock_above(self):
        """Description shows stock is above protected minimum."""
        norm = StockProtectionNorm("test", {"min_stock_pct": 0.40, "original_stock_kg": 300})
        context = make_context(stock_before=200)
        desc = norm.describe(context, "agent_1")
        assert "200kg" in desc
        assert "120kg" in desc
        assert "above" in desc

    def test_describe_when_stock_below(self):
        """Description shows fishing is suspended when below threshold."""
        norm = StockProtectionNorm("test", {"min_stock_pct": 0.40, "original_stock_kg": 300})
        context = make_context(stock_before=100)
        desc = norm.describe(context, "agent_1")
        assert "suspended" in desc
        assert "100kg" in desc
        assert "120kg" in desc

    def test_evaluate_allows_all(self):
        """evaluate() always allows the proposed kg (eligibility check happens elsewhere)."""
        norm = StockProtectionNorm("test", {})
        context = make_context(stock_before=100)
        decision = norm.evaluate(context, "agent_1", raw_kg=10, proposed_kg=8)
        assert decision.kept_kg == 8
        assert not decision.violated

    def test_default_params(self):
        """Default params are 40% of 300kg."""
        norm = StockProtectionNorm("test", {})
        context = make_context(stock_before=100)
        # 100 < 120 (40% of 300), so should be ineligible
        assert norm.is_eligible(context, "agent_1") is False
