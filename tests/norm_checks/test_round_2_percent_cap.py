"""Tests for Round 2: Percent Stock Cap Norm.

Policy: No fisher may take more than 10% of the lake's current stock per trip.
"""

import pytest

from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.percent_stock_cap import PercentStockCapNorm


def _context(stock_kg=300.0, round_number=1, existing_runtime=None, watcher_estimate=None):
    """Create a test context."""
    runtime = {"stock_kg": stock_kg, "rounds": []}
    if watcher_estimate:
        runtime["norms"] = {
            "lake_watcher": {
                "current_estimate_kg": watcher_estimate
            }
        }
    if existing_runtime:
        runtime.update(existing_runtime)
    return HarvestContext.from_state({
        "config": {},
        "fluents": [],
        "runtime": runtime,
        "agents": {},
        "round_number": round_number,
    })


class TestPercentStockCap:
    """Tests for the percent_stock_cap norm."""

    def test_allows_under_limit(self):
        """R2: Catch under 10% of stock is allowed."""
        norm = PercentStockCapNorm(key="cap", params={"percent_limit": 0.10})
        context = _context(watcher_estimate=100.0)  # 10% = 10kg limit
        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)

        assert decision.kept_kg == 5.0
        assert not decision.violated

    def test_trims_over_limit(self):
        """R2: Catch over 10% is trimmed to 10%."""
        norm = PercentStockCapNorm(key="cap", params={"percent_limit": 0.10})
        context = _context(watcher_estimate=100.0)  # 10% = 10kg limit
        decision = norm.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=15.0)

        assert decision.kept_kg == 10.0  # 10% of 100
        assert decision.violated
        assert decision.sanction == "over_stock_limit"

    def test_violation_includes_note(self):
        """R2: Violation note includes excess information."""
        norm = PercentStockCapNorm(key="cap", params={"percent_limit": 0.10})
        context = _context(watcher_estimate=100.0)
        decision = norm.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=15.0)

        assert "10%" in decision.note
        assert "exceeds" in decision.note.lower() or "excess" in decision.note.lower()

    def test_exactly_at_limit(self):
        """R2: Catch exactly at 10% is allowed."""
        norm = PercentStockCapNorm(key="cap", params={"percent_limit": 0.10})
        context = _context(watcher_estimate=100.0)  # 10% = 10kg
        decision = norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)

        assert decision.kept_kg == 10.0
        assert not decision.violated

    def test_dynamic_limit_based_on_stock(self):
        """R2: Limit changes based on stock estimate."""
        norm = PercentStockCapNorm(key="cap", params={"percent_limit": 0.10})

        # Low stock - 10% = 5kg
        context_low = _context(watcher_estimate=50.0)
        decision_low = norm.evaluate(context_low, "agent_0", raw_kg=8.0, proposed_kg=8.0)
        assert decision_low.kept_kg == 5.0

        # High stock - 10% = 50kg
        context_high = _context(watcher_estimate=500.0)
        decision_high = norm.evaluate(context_high, "agent_0", raw_kg=40.0, proposed_kg=40.0)
        assert decision_high.kept_kg == 40.0  # Allowed, under 50kg limit

    def test_describes_constraint(self):
        """R2: Norm describes the percentage constraint."""
        norm = PercentStockCapNorm(key="cap", params={"percent_limit": 0.10})
        context = _context(watcher_estimate=100.0)
        description = norm.describe(context, "agent_0")

        assert "10%" in description
        assert "10.0kg" in description  # 10% of 100

    def test_violation_recorded(self):
        """R4: Violation is recorded for redistribution."""
        norm = PercentStockCapNorm(key="cap", params={"percent_limit": 0.10})
        context = _context(watcher_estimate=100.0, round_number=1)
        decision = NormDecision.violation(
            kept_kg=10.0,
            sanction="over_stock_limit",
            note="Catch of 15.0kg exceeds 10%"
        )

        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)

        state = context.norm_state("cap")
        violations = state.get("violations", [])
        assert len(violations) == 1
        assert violations[0]["agent_id"] == "agent_0"

    def test_defaults_to_actual_stock_if_no_estimate(self):
        """R2: Falls back to actual stock if no watcher estimate."""
        norm = PercentStockCapNorm(key="cap", params={"percent_limit": 0.10})
        context = _context(stock_kg=200.0)  # No watcher_estimate set
        decision = norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)

        # Should use stock_before (200.0) * 0.10 = 20.0 as limit
        assert decision.kept_kg == 20.0
