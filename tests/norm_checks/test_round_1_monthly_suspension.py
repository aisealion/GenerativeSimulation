"""Tests for Round 1: Monthly Stock Measurement and Community Suspension.

Policy: Monthly stock measurements trigger a one-week suspension if below 200 kg.
"""

import pytest

from engine.norms.context import HarvestContext
from norms.monthly_stock_suspension import MonthlyStockSuspensionNorm


def _context(stock_kg=300.0, round_number=1, existing_runtime=None):
    """Create a test context."""
    runtime = {"stock_kg": stock_kg, "rounds": []}
    if existing_runtime:
        runtime.update(existing_runtime)
    return HarvestContext.from_state({
        "config": {},
        "fluents": [],
        "runtime": runtime,
        "agents": {},
        "round_number": round_number,
    })


class TestMonthlyStockSuspension:
    """Tests for the monthly_stock_suspension norm."""

    def test_measurement_at_interval(self):
        """R6: Measurement occurs at monthly interval (every 30 rounds)."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={
            "measurement_interval_rounds": 30
        })
        context = _context(stock_kg=250.0, round_number=30)

        norm.on_round_start(context)

        state = context.norm_state("suspension")
        assert state["last_measurement_round"] == 30
        assert len(state["measurement_history"]) == 1

    def test_no_measurement_between_intervals(self):
        """R6: No measurement occurs between monthly intervals."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={
            "measurement_interval_rounds": 30
        })
        context = _context(stock_kg=250.0, round_number=15)

        norm.on_round_start(context)

        state = context.norm_state("suspension")
        # last_measurement_round should still be 0 (initialized but not updated)
        assert state.get("last_measurement_round", 0) == 0

    def test_suspension_triggered_below_threshold(self):
        """R6/R7: Suspension triggered when stock < 200kg."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={
            "threshold_kg": 200.0,
            "suspension_duration_rounds": 7
        })
        context = _context(stock_kg=150.0, round_number=30)

        norm.on_round_start(context)

        state = context.norm_state("suspension")
        assert state["suspension_end_round"] == 37  # 30 + 1 + 7 - 1 = 37

    def test_no_suspension_above_threshold(self):
        """R6/R7: No suspension when stock >= 200kg."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={
            "threshold_kg": 200.0
        })
        context = _context(stock_kg=250.0, round_number=30)

        norm.on_round_start(context)

        state = context.norm_state("suspension")
        # suspension_end_round should not be set or be in the past
        assert state.get("suspension_end_round", 0) <= 30

    def test_suspension_makes_agents_ineligible(self):
        """R7: During suspension, all agents are ineligible."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={})
        runtime = {
            "norms": {
                "suspension": {
                    "suspension_end_round": 40
                }
            }
        }
        context = _context(round_number=35, existing_runtime=runtime)

        assert norm.is_eligible(context, "agent_0") is False
        assert norm.is_eligible(context, "agent_1") is False

    def test_suspension_expires(self):
        """R7: Suspension expires after one week (7 rounds)."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={})
        runtime = {
            "norms": {
                "suspension": {
                    "suspension_end_round": 40
                }
            }
        }
        context = _context(round_number=41, existing_runtime=runtime)

        assert norm.is_eligible(context, "agent_0") is True

    def test_describes_active_suspension(self):
        """R7: Active suspension is described to agents."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={})
        runtime = {
            "norms": {
                "suspension": {
                    "suspension_end_round": 40,
                    "last_measurement_round": 30
                }
            }
        }
        context = _context(round_number=35, existing_runtime=runtime)

        description = norm.describe(context, "agent_0")
        assert description is not None
        assert "suspension" in description.lower()

    def test_measurement_recorded_correctly(self):
        """R6: Measurement details are recorded accurately."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={
            "threshold_kg": 200.0
        })
        context = _context(stock_kg=150.0, round_number=30)

        norm.on_round_start(context)

        state = context.norm_state("suspension")
        measurement = state["measurement_history"][0]
        assert measurement["round"] == 30
        assert measurement["stock_kg"] == 150.0
        assert measurement["threshold_kg"] == 200.0
        assert measurement["below_threshold"] is True
        assert measurement["suspension_imposed"] is True
