"""Independent evaluation tests for Round 5 norm implementation.

This file tests the sustenance_cap_with_obligation norm against all requirements
from state/norm_specs/round_5.md without relying on the implementer's tests.

Requirements tested:
- R5.1: Individual Per-Trip Cap (12kg)
- R5.2: Self-Sustenance Minimum Floor (1kg)
- R5.3: Excess Return to Lake
- R5.4: Shared Ledger Logging
- R5.5: Violation Detection and Communal Obligation
- R5.6: Weekly Community Council Review
- R5.7: Two-Trip Obligation Satisfaction
- R5.8: Automatic Obligation Fulfillment
- R5.9: Communal Pool Tracking
- R5.10: Obligation Expiration and Forced Payment
- R5.11: Agent-Facing Description
"""

import pytest
from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.sustenance_cap_with_obligation import SustenanceCapWithObligationNorm


class TestRound5IndependentEvaluation:
    """Independent evaluation test cases for Round 5 norms."""

    def create_context(self, round_number=1, stock_before=150.0, runtime_norms=None):
        """Create a test HarvestContext."""
        config = {
            "norms": [
                {
                    "type": "sustenance_cap_with_obligation",
                    "cap_kg": 12,
                    "min_keep_kg": 1,
                    "obligation_trips": 2,
                    "auto_deduction_rate": 0.10,
                    "review_frequency_rounds": 7,
                }
            ]
        }
        runtime = {"norms": runtime_norms or {}}
        return HarvestContext(
            config=config,
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=round_number,
            stock_before=stock_before,
        )

    # ============================================================================
    # R5.1: Individual Per-Trip Cap (12kg)
    # ============================================================================

    def test_r5_1_fixed_cap_12kg(self):
        """TC-R5-1: Fixed 12 kg cap applies regardless of stock."""
        context = self.create_context(stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=15.0, proposed_kg=15.0)

        # Cap = 12 kg, kept = 12 kg, returned = 3 kg
        # Violation = true, obligation = 3 kg
        assert decision.kept_kg == 12.0, f"Expected 12 kg kept, got {decision.kept_kg}"
        assert decision.violated is True, "Expected violation flag to be True"

    def test_r5_1_cap_not_dynamic(self):
        """Cap is fixed at 12 kg regardless of stock level."""
        # Test with high stock
        context_high = self.create_context(stock_before=200.0)
        norm_high = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm_high.on_round_start(context_high)
        decision_high = norm_high.evaluate(context_high, "agent_1", raw_kg=15.0, proposed_kg=15.0)

        # Test with low stock
        context_low = self.create_context(stock_before=50.0)
        norm_low = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm_low.on_round_start(context_low)
        decision_low = norm_low.evaluate(context_low, "agent_1", raw_kg=15.0, proposed_kg=15.0)

        # Both should have same cap
        assert decision_high.kept_kg == 12.0, f"High stock: Expected 12 kg, got {decision_high.kept_kg}"
        assert decision_low.kept_kg == 12.0, f"Low stock: Expected 12 kg, got {decision_low.kept_kg}"

    def test_r5_1_exactly_at_cap_no_violation(self):
        """Exactly at 12 kg is not a violation."""
        context = self.create_context(stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=12.0, proposed_kg=12.0)

        assert decision.violated is False, "Exactly at cap should not be violation"
        assert decision.kept_kg == 12.0, f"Expected 12 kg kept, got {decision.kept_kg}"

    # ============================================================================
    # R5.2: Self-Sustenance Minimum Floor (1kg)
    # ============================================================================

    def test_r5_2_minimum_floor_not_triggered(self):
        """TC-R5-3: Self-sustenance floor (1 kg) not triggered when kept > 1 kg."""
        context = self.create_context(stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)
        # Agent catches 8 kg (under 12 kg cap)
        decision = norm.evaluate(context, "agent_1", raw_kg=8.0, proposed_kg=8.0)

        assert decision.kept_kg == 8.0, f"Expected 8 kg kept, got {decision.kept_kg}"
        assert decision.violated is False, "Should not be a violation"

    def test_r5_2_floor_respects_actual_catch(self):
        """TC-R5-2: Floor cannot create fish - if catch < 1 kg, keep actual catch."""
        context = self.create_context(stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=0.5, proposed_kg=0.5)

        # Can't create fish - keep actual catch
        assert decision.kept_kg == 0.5, f"Expected 0.5 kg kept, got {decision.kept_kg}"

    def test_r5_2_floor_at_exactly_1kg(self):
        """Exactly 1 kg catch respects floor."""
        context = self.create_context(stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=1.0, proposed_kg=1.0)

        assert decision.kept_kg == 1.0, f"Expected 1 kg kept, got {decision.kept_kg}"

    # ============================================================================
    # R5.3: Excess Return to Lake
    # ============================================================================

    def test_r5_3_excess_returned_to_lake(self):
        """Excess fish above 12 kg cap is returned to lake."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=15.0, proposed_kg=15.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": 12.0, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        # Stock after harvest: 150 - 12 = 138
        # Stock after return: 138 + 3 = 141
        assert context.stock_override_kg is not None, "Expected stock override to be set"
        expected_stock = 141.0
        assert context.stock_override_kg == expected_stock, \
            f"Expected stock override of {expected_stock}, got {context.stock_override_kg}"

    def test_r5_3_no_excess_when_under_cap(self):
        """No excess returned when under cap."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=10.0, proposed_kg=10.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 0.6, "harvested_kg": 10.0, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        # Stock override should not be set (no excess to return)
        # Or if set, should be same as after harvest
        if context.stock_override_kg is not None:
            expected_stock = 140.0  # 150 - 10
            assert context.stock_override_kg == expected_stock, \
                f"Expected stock {expected_stock}, got {context.stock_override_kg}"

    # ============================================================================
    # R5.4: Shared Ledger Logging
    # ============================================================================

    def test_r5_4_ledger_records_all_fields(self):
        """Ledger records all required fields for each entry."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)
        norm.evaluate(context, "agent_1", raw_kg=15.0, proposed_kg=15.0)

        norm_state = context.norm_state("sustenance_cap_with_obligation")
        ledger = norm_state.get("ledger", [])

        assert len(ledger) == 1, "Expected one ledger entry"
        entry = ledger[0]

        # Check all required fields
        assert "round" in entry, "Missing 'round' field"
        assert "agent_id" in entry, "Missing 'agent_id' field"
        assert "raw_catch" in entry, "Missing 'raw_catch' field"
        assert "obligation_deducted" in entry, "Missing 'obligation_deducted' field"
        assert "kept" in entry, "Missing 'kept' field"
        assert "returned_to_lake" in entry, "Missing 'returned_to_lake' field"
        assert "obligation_accrued" in entry, "Missing 'obligation_accrued' field"
        assert "violation" in entry, "Missing 'violation' field"

        # Check values
        assert entry["round"] == 1
        assert entry["agent_id"] == "agent_1"
        assert entry["raw_catch"] == 15.0
        assert entry["obligation_deducted"] == 0.0  # No existing obligation
        assert entry["kept"] == 12.0  # Capped at 12 kg
        assert entry["returned_to_lake"] == 3.0  # 15 - 12
        assert entry["obligation_accrued"] == 0.0  # Set in on_agent_settled
        assert entry["violation"] is True

    def test_r5_4_ledger_accumulates_entries(self):
        """Ledger accumulates entries across multiple agents."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)
        norm.evaluate(context, "agent_1", raw_kg=15.0, proposed_kg=15.0)
        norm.evaluate(context, "agent_2", raw_kg=10.0, proposed_kg=10.0)

        norm_state = context.norm_state("sustenance_cap_with_obligation")
        ledger = norm_state.get("ledger", [])

        assert len(ledger) == 2, f"Expected 2 ledger entries, got {len(ledger)}"

    # ============================================================================
    # R5.5: Violation Detection and Communal Obligation
    # ============================================================================

    def test_r5_5_violation_creates_obligation(self):
        """TC-R5-1: Violation creates communal obligation for excess amount."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=15.0, proposed_kg=15.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        norm_state = context.norm_state("sustenance_cap_with_obligation")
        obligations = norm_state.get("obligations", {})

        assert "agent_1" in obligations, "Expected communal obligation for agent_1"
        assert obligations["agent_1"]["amount"] == 3.0, \
            f"Expected 3 kg obligation, got {obligations['agent_1']['amount']}"
        assert obligations["agent_1"]["trips_remaining"] == 2, \
            f"Expected 2 trips remaining, got {obligations['agent_1']['trips_remaining']}"

    def test_r5_5_no_violation_no_obligation(self):
        """No obligation created when under cap."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=10.0, proposed_kg=10.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        norm_state = context.norm_state("sustenance_cap_with_obligation")
        obligations = norm_state.get("obligations", {})

        assert "agent_1" not in obligations, "Should not have obligation when under cap"

    def test_r5_5_exact_obligation_amount(self):
        """Obligation equals exact excess over 12 kg."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        norm_state = context.norm_state("sustenance_cap_with_obligation")
        obligations = norm_state.get("obligations", {})

        assert obligations["agent_1"]["amount"] == 8.0, \
            f"Expected 8 kg obligation (20-12), got {obligations['agent_1']['amount']}"

    # ============================================================================
    # R5.6: Weekly Community Council Review
    # ============================================================================

    def test_r5_6_weekly_review_at_round_7(self):
        """TC-R5-7: Weekly review occurs every 7 rounds."""
        context = self.create_context(round_number=7, stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)

        norm_state = context.norm_state("sustenance_cap_with_obligation")
        last_review = norm_state.get("last_review_round")
        review_occurred = norm_state.get("weekly_review_occurred")

        assert last_review == 7, f"Expected last review at round 7, got {last_review}"
        assert review_occurred is True, "Expected weekly_review_occurred to be True"

    def test_r5_6_no_review_at_other_rounds(self):
        """No weekly review at rounds not divisible by 7."""
        context = self.create_context(round_number=6, stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)

        norm_state = context.norm_state("sustenance_cap_with_obligation")
        review_occurred = norm_state.get("weekly_review_occurred")

        assert review_occurred is False, "Should not have weekly review at round 6"

    def test_r5_6_multiple_weekly_reviews(self):
        """Weekly reviews occur at rounds 7, 14, 21, etc."""
        for round_num in [7, 14, 21, 28]:
            context = self.create_context(round_number=round_num, stock_before=150.0)
            norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
            norm.on_round_start(context)

            norm_state = context.norm_state("sustenance_cap_with_obligation")
            assert norm_state.get("weekly_review_occurred") is True, \
                f"Expected review at round {round_num}"

    # ============================================================================
    # R5.7: Two-Trip Obligation Satisfaction
    # ============================================================================

    def test_r5_7_obligation_deducted_on_next_trip(self):
        """TC-R5-4: Obligation deducted on next trip."""
        # Round 1: Create obligation
        context1 = self.create_context(round_number=1, stock_before=150.0)
        norm1 = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm1.on_round_start(context1)
        decision1 = norm1.evaluate(context1, "agent_1", raw_kg=15.0, proposed_kg=15.0)
        norm1.on_agent_settled(context1, "agent_1", decision1, decision1.kept_kg)

        # Round 2: Deduct from obligation
        context2 = self.create_context(round_number=2, stock_before=150.0)
        context2.runtime["norms"]["sustenance_cap_with_obligation"] = {
            "obligations": {"agent_1": {"amount": 3.0, "trips_remaining": 2, "created_round": 1}},
        }

        norm2 = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm2.on_round_start(context2)  # This decrements trips_remaining to 1
        decision2 = norm2.evaluate(context2, "agent_1", raw_kg=20.0, proposed_kg=20.0)

        # 10% of 20 kg = 2 kg deduction
        # 20 - 2 = 18, capped to 12
        assert decision2.kept_kg == 12.0, f"Expected 12 kg kept, got {decision2.kept_kg}"

        # Check that deduction was recorded
        norm_state = context2.norm_state("sustenance_cap_with_obligation")
        assert norm_state["obligations"]["agent_1"]["amount"] == 1.0, \
            f"Expected 1 kg remaining obligation, got {norm_state['obligations']['agent_1']['amount']}"

    def test_r5_7_obligation_fully_cleared(self):
        """TC-R5-5: Obligation fully cleared when deduction exceeds amount."""
        # Round 1: Create small obligation
        context1 = self.create_context(round_number=1, stock_before=150.0)
        norm1 = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm1.on_round_start(context1)
        decision1 = norm1.evaluate(context1, "agent_1", raw_kg=14.0, proposed_kg=14.0)
        norm1.on_agent_settled(context1, "agent_1", decision1, decision1.kept_kg)

        # Obligation = 2 kg (14 - 12)

        # Round 2: Large catch clears obligation
        context2 = self.create_context(round_number=2, stock_before=150.0)
        context2.runtime["norms"]["sustenance_cap_with_obligation"] = {
            "obligations": {"agent_1": {"amount": 2.0, "trips_remaining": 2, "created_round": 1}},
        }

        norm2 = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm2.on_round_start(context2)
        decision2 = norm2.evaluate(context2, "agent_1", raw_kg=25.0, proposed_kg=25.0)

        # 10% of 25 = 2.5 kg deduction, but obligation is only 2 kg
        # So 2 kg deducted, obligation cleared

        norm_state = context2.norm_state("sustenance_cap_with_obligation")
        assert "agent_1" not in norm_state.get("obligations", {}), \
            "Obligation should be cleared"

    # ============================================================================
    # R5.8: Automatic Obligation Fulfillment
    # ============================================================================

    def test_r5_8_auto_deduction_rate(self):
        """10% of catch automatically deducted toward obligation."""
        context = self.create_context(round_number=2, stock_before=150.0)
        context.runtime["norms"]["sustenance_cap_with_obligation"] = {
            "obligations": {"agent_1": {"amount": 5.0, "trips_remaining": 2, "created_round": 1}},
        }

        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)

        # 10% of 20 = 2 kg deducted
        # 20 - 2 = 18, capped to 12
        assert decision.kept_kg == 12.0, f"Expected 12 kg kept, got {decision.kept_kg}"

    def test_r5_8_deduction_applied_before_cap(self):
        """Obligation deduction is applied before the 12 kg cap."""
        context = self.create_context(round_number=2, stock_before=150.0)
        context.runtime["norms"]["sustenance_cap_with_obligation"] = {
            "obligations": {"agent_1": {"amount": 5.0, "trips_remaining": 2, "created_round": 1}},
        }

        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=15.0, proposed_kg=15.0)

        # Order: 10% deduction (1.5 kg) -> 13.5 remaining -> cap to 12
        assert decision.kept_kg == 12.0, f"Expected 12 kg kept, got {decision.kept_kg}"

    # ============================================================================
    # R5.9: Communal Pool Tracking
    # ============================================================================

    def test_r5_9_communal_pool_tracks_deductions(self):
        """Communal pool tracks obligation deductions."""
        context = self.create_context(round_number=2, stock_before=150.0)
        context.runtime["norms"]["sustenance_cap_with_obligation"] = {
            "obligations": {"agent_1": {"amount": 5.0, "trips_remaining": 2, "created_round": 1}},
            "communal_pool_kg": 0.0,
        }

        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        norm_state = context.norm_state("sustenance_cap_with_obligation")
        communal_pool = norm_state.get("communal_pool_kg", 0)

        # 10% of 20 = 2 kg deducted and added to pool
        assert communal_pool == 2.0, f"Expected communal pool of 2 kg, got {communal_pool}"

    def test_r5_9_communal_pool_accumulates(self):
        """TC-R5-9: Communal pool accumulates across rounds."""
        # Start with existing pool
        context = self.create_context(round_number=2, stock_before=150.0)
        context.runtime["norms"]["sustenance_cap_with_obligation"] = {
            "obligations": {"agent_1": {"amount": 5.0, "trips_remaining": 2, "created_round": 1}},
            "communal_pool_kg": 3.0,  # From previous rounds
        }

        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        norm_state = context.norm_state("sustenance_cap_with_obligation")
        communal_pool = norm_state.get("communal_pool_kg", 0)

        # 3 + 2 = 5 kg
        assert communal_pool == 5.0, f"Expected communal pool of 5 kg, got {communal_pool}"

    # ============================================================================
    # R5.10: Obligation Expiration and Forced Payment
    # ============================================================================

    def test_r5_10_obligation_expires_after_2_trips(self):
        """TC-R5-6: Obligation expires and is forcibly paid after 2 trips."""
        # Round 3: Obligation with 0 trips remaining
        context = self.create_context(round_number=3, stock_before=150.0)
        context.runtime["norms"]["sustenance_cap_with_obligation"] = {
            "obligations": {"agent_1": {"amount": 2.0, "trips_remaining": 0, "created_round": 1}},
        }

        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=10.0, proposed_kg=10.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 0.6, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        # Check forced payment was applied
        assert round_results["agent_1"]["harvested_kg"] == 8.0, \
            f"Expected 8 kg after forced payment, got {round_results['agent_1']['harvested_kg']}"

        # Obligation should be cleared
        norm_state = context.norm_state("sustenance_cap_with_obligation")
        assert "agent_1" not in norm_state.get("obligations", {}), \
            "Expired obligation should be cleared"

    def test_r5_10_trips_remaining_decrements(self):
        """Trips remaining decrements each round."""
        # Start with 2 trips remaining
        context = self.create_context(round_number=2, stock_before=150.0)
        context.runtime["norms"]["sustenance_cap_with_obligation"] = {
            "obligations": {"agent_1": {"amount": 3.0, "trips_remaining": 2, "created_round": 1}},
        }

        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm.on_round_start(context)

        norm_state = context.norm_state("sustenance_cap_with_obligation")
        trips_remaining = norm_state["obligations"]["agent_1"]["trips_remaining"]

        assert trips_remaining == 1, f"Expected 1 trip remaining, got {trips_remaining}"

    # ============================================================================
    # R5.11: Agent-Facing Description
    # ============================================================================

    def test_r5_11_description_includes_cap(self):
        """Description includes the 12 kg cap."""
        context = self.create_context(stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "12" in description, "Description should mention 12 kg cap"

    def test_r5_11_description_includes_minimum(self):
        """Description includes the 1 kg minimum."""
        context = self.create_context(stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "1" in description, "Description should mention 1 kg minimum"

    def test_r5_11_description_includes_obligation(self):
        """Description includes outstanding obligation info."""
        context = self.create_context(stock_before=150.0)
        context.runtime["norms"]["sustenance_cap_with_obligation"] = {
            "obligations": {"agent_1": {"amount": 3.0, "trips_remaining": 2, "created_round": 1}},
        }

        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "COMMUNAL OBLIGATION" in description, "Should mention communal obligation"
        assert "3.0" in description or "3" in description, "Should mention obligation amount"
        assert "2" in description, "Should mention trips remaining"

    def test_r5_11_description_includes_communal_pool(self):
        """Description includes communal pool total."""
        context = self.create_context(stock_before=150.0)
        context.runtime["norms"]["sustenance_cap_with_obligation"] = {
            "communal_pool_kg": 5.0,
        }

        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "communal pool" in description.lower(), "Should mention communal pool"
        assert "5.0" in description or "5" in description, "Should mention pool amount"

    def test_r5_11_description_includes_weekly_review(self):
        """Description includes weekly review info when recent."""
        context = self.create_context(round_number=8, stock_before=150.0)
        context.runtime["norms"]["sustenance_cap_with_obligation"] = {
            "last_review_round": 7,
        }

        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "review" in description.lower(), "Should mention review"

    def test_r5_11_description_includes_ledger(self):
        """Description includes recent ledger entries."""
        context = self.create_context(round_number=3, stock_before=150.0)
        context.runtime["norms"]["sustenance_cap_with_obligation"] = {
            "ledger": [
                {"round": 1, "agent_id": "agent_1", "raw_catch": 15.0, "obligation_deducted": 0.0,
                 "kept": 12.0, "returned_to_lake": 3.0, "obligation_accrued": 0.0, "violation": True},
                {"round": 2, "agent_id": "agent_1", "raw_catch": 10.0, "obligation_deducted": 0.0,
                 "kept": 10.0, "returned_to_lake": 0.0, "obligation_accrued": 0.0, "violation": False},
            ]
        }

        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "Round 1" in description or "Round 2" in description, \
            "Should include recent ledger rounds"

    # ============================================================================
    # Additional Edge Cases
    # ============================================================================

    def test_multiple_agents_independent_obligations(self):
        """TC-R5-8: Multiple agents with independent obligations."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})

        norm.on_round_start(context)

        # Agent A: No violation
        decision_a = norm.evaluate(context, "agent_1", raw_kg=10.0, proposed_kg=10.0)
        norm.on_agent_settled(context, "agent_1", decision_a, decision_a.kept_kg)

        # Agent B: 3 kg obligation
        decision_b = norm.evaluate(context, "agent_2", raw_kg=15.0, proposed_kg=15.0)
        norm.on_agent_settled(context, "agent_2", decision_b, decision_b.kept_kg)

        # Agent C: 8 kg obligation
        decision_c = norm.evaluate(context, "agent_3", raw_kg=20.0, proposed_kg=20.0)
        norm.on_agent_settled(context, "agent_3", decision_c, decision_c.kept_kg)

        norm_state = context.norm_state("sustenance_cap_with_obligation")
        obligations = norm_state.get("obligations", {})

        assert "agent_1" not in obligations, "Agent A should not have obligation"
        assert obligations.get("agent_2", {}).get("amount") == 3.0, "Agent B should have 3 kg obligation"
        assert obligations.get("agent_3", {}).get("amount") == 8.0, "Agent C should have 8 kg obligation"

    def test_floor_with_obligation_deduction(self):
        """TC-R5-10: 1 kg floor respected even with obligation deductions."""
        context = self.create_context(round_number=2, stock_before=150.0)
        context.runtime["norms"]["sustenance_cap_with_obligation"] = {
            "obligations": {"agent_1": {"amount": 1.0, "trips_remaining": 2, "created_round": 1}},
        }

        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm.on_round_start(context)

        # Agent catches small amount
        decision = norm.evaluate(context, "agent_1", raw_kg=2.0, proposed_kg=2.0)

        # 10% of 2 = 0.2 kg deduction
        # 2 - 0.2 = 1.8, no cap (under 12), above 1 kg floor
        assert decision.kept_kg == 1.8, f"Expected 1.8 kg kept, got {decision.kept_kg}"
        assert decision.kept_kg >= 1.0, "Kept amount should respect 1 kg floor"

    def test_floor_cannot_create_fish(self):
        """Floor cannot create fish when catch is below 1 kg."""
        context = self.create_context(round_number=2, stock_before=150.0)
        context.runtime["norms"]["sustenance_cap_with_obligation"] = {
            "obligations": {"agent_1": {"amount": 1.0, "trips_remaining": 2, "created_round": 1}},
        }

        norm = SustenanceCapWithObligationNorm(key="sustenance_cap_with_obligation", params={})
        norm.on_round_start(context)

        # Agent catches less than 1 kg
        decision = norm.evaluate(context, "agent_1", raw_kg=0.5, proposed_kg=0.5)

        # 10% of 0.5 = 0.05 kg deduction
        # 0.5 - 0.05 = 0.45, but can't go below 0 or create fish
        # Actually we can't create fish, so agent keeps actual catch minus deduction
        # But deduction shouldn't exceed available catch
        assert decision.kept_kg <= 0.5, f"Cannot keep more than caught, got {decision.kept_kg}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
