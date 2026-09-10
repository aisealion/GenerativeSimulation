"""Integration tests for Round 1: Full norm system.

Tests that all norms work together correctly.
"""

import pytest

import engine.norms.registry as registry
import actions.harvest as harvest_module
from engine.norms.engine import NormEngine
from engine.norms.context import HarvestContext
from norms.catch_cap import CatchCapNorm
from norms.mandatory_reserve import MandatoryReserveNorm
from norms.violation_handler import ViolationHandlerNorm
from norms.repeated_violation_ban import RepeatedViolationBanNorm
from norms.monthly_stock_suspension import MonthlyStockSuspensionNorm


# Register our norm types for testing
TEST_NORM_TYPES = {
    "catch_cap": CatchCapNorm,
    "mandatory_reserve": MandatoryReserveNorm,
    "violation_handler": ViolationHandlerNorm,
    "repeated_violation_ban": RepeatedViolationBanNorm,
    "monthly_stock_suspension": MonthlyStockSuspensionNorm,
}


def _fake_call_fisher_agent(agent_id, round_number, action_name, **fields):
    """Return high effort to trigger violations."""
    return {"effort": 1.0, "reasoning": "test"}


def _state(norms_config=None, round_number=1, stock_kg=300.0):
    """Create test state."""
    return {
        "config": {"norms": norms_config or []},
        "fluents": [],
        "runtime": {"stock_kg": stock_kg, "rounds": []},
        "agents": {
            "agent_0": {"name": "Kai", "personality_traits": ""},
            "agent_1": {"name": "Mara", "personality_traits": ""},
        },
        "round_number": round_number,
    }


class TestIntegration:
    """Integration tests for the full norm system."""

    def test_catch_cap_norm_alone(self, monkeypatch):
        """Integration: Catch cap alone trims catches over 5kg."""
        monkeypatch.setattr(registry, "NORM_TYPES", TEST_NORM_TYPES)
        monkeypatch.setattr(harvest_module, "call_fisher_agent", _fake_call_fisher_agent)

        state = _state(norms_config=[{"type": "catch_cap", "limit_kg": 5.0}])
        record = harvest_module.ACTION.run(state)

        # Both agents should be capped at 5kg
        assert record["agents"]["agent_0"]["harvested_kg"] <= 5.0
        assert record["agents"]["agent_1"]["harvested_kg"] <= 5.0

    def test_violation_counted_for_over_cap(self, monkeypatch):
        """Integration: Over-cap violations are recorded."""
        monkeypatch.setattr(registry, "NORM_TYPES", TEST_NORM_TYPES)
        monkeypatch.setattr(harvest_module, "call_fisher_agent", _fake_call_fisher_agent)

        state = _state(norms_config=[
            {"type": "catch_cap", "limit_kg": 5.0},
            {"type": "violation_handler", "penalty_kg": 2.0},
        ])
        record = harvest_module.ACTION.run(state)

        # Check that violation was recorded
        vh_state = state["runtime"]["norms"]["violation_handler"]
        assert "violations" in vh_state
        # With high effort, should have caught more than 5kg and triggered violation

    def test_norms_in_correct_order(self, monkeypatch):
        """Integration: Norms are applied in config order."""
        monkeypatch.setattr(registry, "NORM_TYPES", TEST_NORM_TYPES)

        # Create engine with norms in order
        config = {
            "norms": [
                {"type": "catch_cap", "limit_kg": 5.0},
                {"type": "violation_handler"},
            ]
        }
        engine = NormEngine.from_config(config)

        # Verify order
        assert len(engine.norms) == 2
        assert isinstance(engine.norms[0], CatchCapNorm)
        assert isinstance(engine.norms[1], ViolationHandlerNorm)

    def test_constraint_descriptions_combined(self, monkeypatch):
        """Integration: Multiple norms combine their descriptions."""
        monkeypatch.setattr(registry, "NORM_TYPES", TEST_NORM_TYPES)

        config = {
            "norms": [
                {"type": "catch_cap", "limit_kg": 5.0},
                {"type": "monthly_stock_suspension"},
            ]
        }
        engine = NormEngine.from_config(config)
        context = HarvestContext.from_state({
            "config": config,
            "fluents": [],
            "runtime": {"stock_kg": 300.0, "rounds": []},
            "agents": {},
            "round_number": 1,
        })

        constraints = engine.describe_constraints(context, "agent_0")

        # Should contain parts from both norms
        assert "5kg" in constraints
        assert "limit" in constraints

    def test_full_round_1_norm_stack(self, monkeypatch):
        """Integration: Complete Round 1 norm stack runs without errors."""
        monkeypatch.setattr(registry, "NORM_TYPES", TEST_NORM_TYPES)
        monkeypatch.setattr(harvest_module, "call_fisher_agent", _fake_call_fisher_agent)

        state = _state(norms_config=[
            {"type": "catch_cap", "limit_kg": 5.0},
            {"type": "mandatory_reserve", "reserve_kg": 1.0},
            {"type": "violation_handler", "penalty_kg": 2.0},
            {"type": "repeated_violation_ban", "violation_threshold": 2, "ban_duration_rounds": 7},
            {"type": "monthly_stock_suspension", "threshold_kg": 200.0, "measurement_interval_rounds": 30, "suspension_duration_rounds": 7},
        ])

        # Run a few rounds
        for round_num in range(1, 6):
            state["round_number"] = round_num
            record = harvest_module.ACTION.run(state)

            # Verify basic expectations
            assert "agents" in record
            for agent_id in ["agent_0", "agent_1"]:
                assert agent_id in record["agents"]
                assert "harvested_kg" in record["agents"][agent_id]
                # Catch should never exceed 5kg
                assert record["agents"][agent_id]["harvested_kg"] <= 5.0

    def test_monthly_measurement_at_round_30(self, monkeypatch):
        """Integration: Monthly measurement occurs at round 30."""
        monkeypatch.setattr(registry, "NORM_TYPES", TEST_NORM_TYPES)
        monkeypatch.setattr(harvest_module, "call_fisher_agent", _fake_call_fisher_agent)

        # Start with low stock to trigger suspension
        state = _state(
            norms_config=[
                {"type": "monthly_stock_suspension", "threshold_kg": 200.0, "measurement_interval_rounds": 30},
            ],
            round_number=30,
            stock_kg=150.0  # Below threshold
        )

        record = harvest_module.ACTION.run(state)

        # Check that measurement was recorded
        suspension_state = state["runtime"]["norms"]["monthly_stock_suspension"]
        assert suspension_state["last_measurement_round"] == 30
        assert suspension_state["suspension_end_round"] == 37  # 30 + 1 + 7 - 1

    def test_ban_prevents_participation(self, monkeypatch):
        """Integration: Banned agents cannot participate."""
        monkeypatch.setattr(registry, "NORM_TYPES", TEST_NORM_TYPES)

        # Pre-seed a ban for agent_0
        state = _state(
            norms_config=[
                {"type": "repeated_violation_ban"},
            ],
            round_number=5
        )
        state["runtime"]["norms"] = {
            "repeated_violation_ban": {
                "agent_0": {"banned_until_round": 10}
            }
        }

        engine = NormEngine.from_config(state["config"])
        context = HarvestContext.from_state(state)

        # Agent 0 should be ineligible
        assert engine.is_eligible(context, "agent_0") is False
        # Agent 1 should be eligible
        assert engine.is_eligible(context, "agent_1") is True
