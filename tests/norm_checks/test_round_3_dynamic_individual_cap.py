"""Tests for Round 3 dynamic individual cap norm."""

import pytest
from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.dynamic_individual_cap import DynamicIndividualCapNorm


class TestDynamicIndividualCap:
    """Test cases for the dynamic individual cap norm."""

    def create_context(self, round_number=1, stock_before=50.0, config=None):
        """Create a test HarvestContext."""
        if config is None:
            config = {
                "norms": [
                    {"type": "dynamic_individual_cap", "standard_cap_kg": 15, "emergency_cap_kg": 10, "emergency_threshold_kg": 20}
                ]
            }
        return HarvestContext(
            config=config,
            fluents=[],
            runtime={"norms": {}},
            agents={},
            round_number=round_number,
            stock_before=stock_before,
        )

    def test_standard_cap_with_healthy_reserves(self):
        """TC-R3-1: Standard cap applies with healthy reserves."""
        context = self.create_context(stock_before=50.0)
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})

        # Call on_round_start to set up the cap
        norm.on_round_start(context)

        # Agent catches 20 kg
        decision = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)

        assert decision.kept_kg == 15.0
        assert decision.note is not None
        assert "15 kg" in decision.note
        assert "returned" in decision.note.lower()

    def test_emergency_cap_with_low_reserves(self):
        """TC-R3-2: Emergency cap applies with low reserves."""
        context = self.create_context(stock_before=15.0)
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})

        # Call on_round_start to set up the cap
        norm.on_round_start(context)

        # Agent catches 15 kg
        decision = norm.evaluate(context, "agent_1", raw_kg=15.0, proposed_kg=15.0)

        assert decision.kept_kg == 10.0
        assert decision.note is not None
        assert "10 kg" in decision.note or "cap" in decision.note.lower()

    def test_recovery_to_standard_cap(self):
        """TC-R3-3: Recovery to standard cap when reserves increase."""
        # First round with low reserves
        context1 = self.create_context(round_number=1, stock_before=15.0)
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})

        norm.on_round_start(context1)
        cap1 = context1.norm_state("dynamic_individual_cap").get("current_cap")
        assert cap1 == 10  # Emergency cap

        # Second round with healthy reserves
        context2 = self.create_context(round_number=2, stock_before=25.0)
        norm2 = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})

        norm2.on_round_start(context2)
        cap2 = context2.norm_state("dynamic_individual_cap").get("current_cap")
        assert cap2 == 15  # Standard cap

    def test_under_cap_no_adjustment(self):
        """Agent catches less than cap - no adjustment needed."""
        context = self.create_context(stock_before=50.0)
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})

        norm.on_round_start(context)

        # Agent catches 12 kg (under 15 kg cap)
        decision = norm.evaluate(context, "agent_1", raw_kg=12.0, proposed_kg=12.0)

        assert decision.kept_kg == 12.0
        assert not decision.violated

    def test_ledger_recording(self):
        """Ledger records all catches."""
        context = self.create_context(round_number=1, stock_before=50.0)
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})

        norm.on_round_start(context)
        norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.evaluate(context, "agent_2", raw_kg=10.0, proposed_kg=10.0)

        ledger = context.norm_state("dynamic_individual_cap").get("ledger", [])
        assert len(ledger) == 2

        # Check agent_1 entry
        agent1_entry = [e for e in ledger if e["agent_id"] == "agent_1"][0]
        assert agent1_entry["raw_catch"] == 20.0
        assert agent1_entry["kept"] == 15.0
        assert agent1_entry["returned"] == 5.0

    def test_describe_includes_emergency_message(self):
        """Description includes emergency cap message when applicable."""
        context = self.create_context(stock_before=15.0)
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})

        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "EMERGENCY CAP ACTIVE" in description
        assert "10 kg" in description

    def test_describe_includes_ledger(self):
        """Description includes recent ledger entries."""
        context = self.create_context(round_number=3, stock_before=50.0)
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})

        # Manually add ledger entries for rounds 1 and 2
        norm_state = context.norm_state("dynamic_individual_cap")
        norm_state["ledger"] = [
            {"round": 1, "agent_id": "agent_1", "raw_catch": 20.0, "kept": 15.0, "returned": 5.0, "cap_applied": 15},
            {"round": 2, "agent_id": "agent_2", "raw_catch": 18.0, "kept": 15.0, "returned": 3.0, "cap_applied": 15},
        ]

        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "Round 1" in description or "Round 2" in description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
