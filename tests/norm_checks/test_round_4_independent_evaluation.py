"""Independent evaluation tests for Round 4 norm implementation.

This file tests the dynamic_cap_with_penalty norm against all requirements
from state/norm_specs/round_4.md without relying on the implementer's tests.

Requirements tested:
- R4.1: Individual Per-Trip Cap (Dynamic)
- R4.2: Self-Sustenance Minimum Floor
- R4.3: Violation Detection and 1 kg Penalty
- R4.4: Personal Limit Reduction Penalty
- R4.5: Shared Logbook
- R4.6: Communal Pool Tracking
- R4.7: Monthly Stock Review
- R4.8: Excess Return to Lake
- R4.9: Penalty Application Order
- R4.10: Agent-Facing Description
"""

import pytest
from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.dynamic_cap_with_penalty import DynamicCapWithPenaltyNorm


class TestRound4IndependentEvaluation:
    """Independent evaluation test cases for Round 4 norms."""

    def create_context(self, round_number=1, stock_before=150.0, runtime_norms=None):
        """Create a test HarvestContext."""
        config = {
            "norms": [
                {
                    "type": "dynamic_cap_with_penalty",
                    "standard_cap_kg": 15,
                    "emergency_cap_kg": 10,
                    "emergency_threshold_kg": 100,
                    "min_keep_kg": 1,
                    "violation_penalty_kg": 1,
                    "limit_reduction_kg": 5,
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
    # R4.1: Individual Per-Trip Cap (Dynamic)
    # ============================================================================

    def test_r4_1_standard_cap_with_healthy_stock(self):
        """TC-R4-1: Standard cap (15 kg) applies when stock >= 100 kg."""
        context = self.create_context(stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)

        # Cap = 15 kg, kept = 15 kg, returned = 5 kg
        # Violation = true, penalty = 1 kg
        # Final kept = 14 kg (after 1 kg penalty)
        assert decision.kept_kg == 14.0, f"Expected 14 kg kept, got {decision.kept_kg}"
        assert decision.violated is True, "Expected violation flag to be True"
        assert "violation" in (decision.note or "").lower(), "Expected violation in note"

    def test_r4_1_emergency_cap_with_low_stock(self):
        """TC-R4-2: Emergency cap (10 kg) applies when stock < 100 kg."""
        context = self.create_context(stock_before=80.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=15.0, proposed_kg=15.0)

        # Cap = 10 kg, kept = 10 kg, returned = 5 kg
        # Violation = true, penalty = 1 kg
        # Final kept = 9 kg (after 1 kg penalty)
        assert decision.kept_kg == 9.0, f"Expected 9 kg kept, got {decision.kept_kg}"
        assert decision.violated is True, "Expected violation flag to be True"

    def test_r4_1_cap_determined_at_round_start(self):
        """Cap is evaluated at round start and applies uniformly."""
        context = self.create_context(stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)

        # Both agents should have same cap
        decision1 = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        decision2 = norm.evaluate(context, "agent_2", raw_kg=18.0, proposed_kg=18.0)

        assert decision1.kept_kg == 14.0  # 15 cap - 1 penalty
        assert decision2.kept_kg == 14.0  # 15 cap - 1 penalty

    # ============================================================================
    # R4.2: Self-Sustenance Minimum Floor
    # ============================================================================

    def test_r4_2_minimum_floor_not_triggered(self):
        """TC-R4-3: Self-sustenance floor (1 kg) not triggered when kept > 1 kg."""
        context = self.create_context(stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        # Agent catches 8 kg (under 15 kg cap, no penalty)
        decision = norm.evaluate(context, "agent_1", raw_kg=8.0, proposed_kg=8.0)

        assert decision.kept_kg == 8.0, f"Expected 8 kg kept, got {decision.kept_kg}"
        assert decision.violated is False, "Should not be a violation"

    def test_r4_2_floor_applied_when_below_minimum(self):
        """Minimum floor raises kept amount to 1 kg when below."""
        context = self.create_context(stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        # Agent catches 0.5 kg (under cap, no penalty)
        decision = norm.evaluate(context, "agent_1", raw_kg=0.5, proposed_kg=0.5)

        # Should keep actual catch since it's below 1 kg minimum
        # The spec says: "If an agent catches less than 1 kg, they keep what they caught"
        assert decision.kept_kg == 0.5, f"Expected 0.5 kg kept (actual catch), got {decision.kept_kg}"

    def test_r4_2_floor_respects_actual_catch(self):
        """Floor cannot create fish - if catch < 1 kg, keep actual catch."""
        context = self.create_context(stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=0.3, proposed_kg=0.3)

        # Can't create fish - keep actual catch
        assert decision.kept_kg == 0.3, f"Expected 0.3 kg kept, got {decision.kept_kg}"

    # ============================================================================
    # R4.3: Violation Detection and 1 kg Penalty
    # ============================================================================

    def test_r4_3_violation_detected_when_exceeding_cap(self):
        """Violation detected when proposed catch exceeds applicable cap."""
        context = self.create_context(stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)

        assert decision.violated is True, "Expected violation when exceeding cap"
        assert decision.sanction == "limit_reduction", "Expected limit_reduction sanction"

    def test_r4_3_penalty_subtracted_from_kept(self):
        """1 kg penalty is subtracted from agent's kept amount."""
        context = self.create_context(stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        # 20 kg catch, 15 kg cap -> 5 kg returned, 1 kg penalty
        # Final: 15 - 1 = 14 kg
        decision = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)

        assert decision.kept_kg == 14.0, f"Expected 14 kg (15 cap - 1 penalty), got {decision.kept_kg}"

    def test_r4_3_no_violation_when_under_cap(self):
        """No violation when catch is under cap."""
        context = self.create_context(stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=14.0, proposed_kg=14.0)

        assert decision.violated is False, "Should not be violation when under cap"
        assert decision.kept_kg == 14.0, f"Expected 14 kg kept, got {decision.kept_kg}"

    # ============================================================================
    # R4.4: Personal Limit Reduction Penalty
    # ============================================================================

    def test_r4_4_personal_limit_reduction_applied_after_violation(self):
        """TC-R4-5: Personal limit reduced by 5 kg after violation."""
        context1 = self.create_context(round_number=1, stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        # Round 1: Agent violates 15 kg cap
        norm.on_round_start(context1)
        decision1 = norm.evaluate(context1, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.on_agent_settled(context1, "agent_1", decision1, decision1.kept_kg)

        # Personal limit should be set to 10 kg for next round
        norm_state = context1.norm_state("dynamic_cap_with_penalty")
        personal_limits = norm_state.get("personal_limits", {})
        assert "agent_1" in personal_limits, "Expected personal limit penalty for agent_1"
        assert personal_limits["agent_1"]["reduced_limit"] == 10.0, \
            f"Expected reduced limit of 10 kg, got {personal_limits['agent_1']['reduced_limit']}"

    def test_r4_4_reduced_limit_applied_next_trip(self):
        """Reduced limit is applied on the next trip."""
        # Round 1: Set up penalty
        context1 = self.create_context(round_number=1, stock_before=150.0)
        norm1 = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm1.on_round_start(context1)
        decision1 = norm1.evaluate(context1, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm1.on_agent_settled(context1, "agent_1", decision1, decision1.kept_kg)

        # Round 2: Apply reduced limit
        context2 = self.create_context(round_number=2, stock_before=150.0)
        # Copy personal_limits from round 1
        context2.runtime["norms"]["dynamic_cap_with_penalty"] = {
            "personal_limits": {"agent_1": {"reduced_limit": 10.0, "set_in_round": 1}},
            "communal_pool_kg": 1.0,
        }

        norm2 = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm2.on_round_start(context2)

        # Agent catches 12 kg, but personal limit is 10 kg
        decision2 = norm2.evaluate(context2, "agent_1", raw_kg=12.0, proposed_kg=12.0)

        # Should be violation (12 > 10), kept = 10 - 1 = 9 kg
        assert decision2.violated is True, "Expected violation against personal limit"
        assert decision2.kept_kg == 9.0, f"Expected 9 kg kept, got {decision2.kept_kg}"

    def test_r4_4_penalty_clears_after_compliant_trip(self):
        """TC-R4-6: Penalty clears after one compliant trip."""
        # Round 1: Set up penalty
        context1 = self.create_context(round_number=1, stock_before=150.0)
        norm1 = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm1.on_round_start(context1)
        decision1 = norm1.evaluate(context1, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm1.on_agent_settled(context1, "agent_1", decision1, decision1.kept_kg)

        # Round 2: Compliant trip (catches 8 kg under 10 kg personal limit)
        context2 = self.create_context(round_number=2, stock_before=150.0)
        context2.runtime["norms"]["dynamic_cap_with_penalty"] = {
            "personal_limits": {"agent_1": {"reduced_limit": 10.0, "set_in_round": 1}},
            "communal_pool_kg": 1.0,
        }

        norm2 = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm2.on_round_start(context2)
        decision2 = norm2.evaluate(context2, "agent_1", raw_kg=8.0, proposed_kg=8.0)
        norm2.on_agent_settled(context2, "agent_1", decision2, decision2.kept_kg)

        # Penalty should be cleared
        norm_state2 = context2.norm_state("dynamic_cap_with_penalty")
        personal_limits = norm_state2.get("personal_limits", {})
        assert "agent_1" not in personal_limits, "Penalty should clear after compliant trip"

    def test_r4_4_minimum_personal_limit(self):
        """Personal limit cannot go below 1 kg floor."""
        # Simulate agent with very low personal limit
        context = self.create_context(stock_before=150.0)
        context.runtime["norms"]["dynamic_cap_with_penalty"] = {
            "personal_limits": {"agent_1": {"reduced_limit": 1.0, "set_in_round": 1}},
        }

        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm.on_round_start(context)

        # Personal limit should be at minimum 1 kg
        personal_limit = norm._get_personal_limit(context, "agent_1")
        assert personal_limit >= 1.0, f"Personal limit should be >= 1 kg, got {personal_limit}"

    # ============================================================================
    # R4.5: Shared Logbook
    # ============================================================================

    def test_r4_5_logbook_records_all_fields(self):
        """Logbook records all required fields for each entry."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)

        norm_state = context.norm_state("dynamic_cap_with_penalty")
        logbook = norm_state.get("logbook", [])

        assert len(logbook) == 1, "Expected one logbook entry"
        entry = logbook[0]

        # Check all required fields
        assert "round" in entry, "Missing 'round' field"
        assert "agent_id" in entry, "Missing 'agent_id' field"
        assert "raw_catch" in entry, "Missing 'raw_catch' field"
        assert "standard_cap" in entry, "Missing 'standard_cap' field"
        assert "personal_limit" in entry, "Missing 'personal_limit' field"
        assert "kept" in entry, "Missing 'kept' field"
        assert "returned" in entry, "Missing 'returned' field"
        assert "penalty" in entry, "Missing 'penalty' field"
        assert "violated" in entry, "Missing 'violated' field"

        # Check values
        assert entry["round"] == 1
        assert entry["agent_id"] == "agent_1"
        assert entry["raw_catch"] == 20.0
        assert entry["standard_cap"] == 15.0
        assert entry["personal_limit"] == 15.0  # No reduced limit yet
        assert entry["kept"] == 14.0  # 15 cap - 1 penalty
        assert entry["returned"] == 5.0  # 20 - 15 cap
        assert entry["penalty"] == 1.0
        assert entry["violated"] is True

    def test_r4_5_logbook_accumulates_entries(self):
        """Logbook accumulates entries across multiple agents and rounds."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.evaluate(context, "agent_2", raw_kg=10.0, proposed_kg=10.0)

        norm_state = context.norm_state("dynamic_cap_with_penalty")
        logbook = norm_state.get("logbook", [])

        assert len(logbook) == 2, f"Expected 2 logbook entries, got {len(logbook)}"

    # ============================================================================
    # R4.6: Communal Pool Tracking
    # ============================================================================

    def test_r4_6_communal_pool_tracks_penalties(self):
        """Communal pool tracks cumulative penalties across rounds."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        # Set up round results for on_round_end
        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        norm_state = context.norm_state("dynamic_cap_with_penalty")
        communal_pool = norm_state.get("communal_pool_kg", 0)

        assert communal_pool == 1.0, f"Expected communal pool of 1 kg, got {communal_pool}"

    def test_r4_6_communal_pool_accumulates(self):
        """TC-R4-9: Communal pool accumulates 1 kg per violation."""
        # Start with existing pool from previous rounds
        context = self.create_context(round_number=2, stock_before=150.0)
        context.runtime["norms"]["dynamic_cap_with_penalty"] = {
            "communal_pool_kg": 3.0,  # From previous violations
        }

        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm.on_round_start(context)

        # Two agents violate
        decision1 = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.on_agent_settled(context, "agent_1", decision1, decision1.kept_kg)

        decision2 = norm.evaluate(context, "agent_2", raw_kg=18.0, proposed_kg=18.0)
        norm.on_agent_settled(context, "agent_2", decision2, decision2.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision1.kept_kg, "participated": True, "note": None},
            "agent_2": {"effort": 1.0, "harvested_kg": decision2.kept_kg, "participated": True, "note": None},
        }
        norm.on_round_end(context, round_results)

        norm_state = context.norm_state("dynamic_cap_with_penalty")
        communal_pool = norm_state.get("communal_pool_kg", 0)

        assert communal_pool == 5.0, f"Expected communal pool of 5 kg (3 + 2), got {communal_pool}"

    def test_r4_6_communal_pool_persists_without_violations(self):
        """Pool persists when no violations occur."""
        context = self.create_context(round_number=2, stock_before=150.0)
        context.runtime["norms"]["dynamic_cap_with_penalty"] = {
            "communal_pool_kg": 5.0,
        }

        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm.on_round_start(context)

        # No violations this round
        decision = norm.evaluate(context, "agent_1", raw_kg=10.0, proposed_kg=10.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 0.6, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        norm_state = context.norm_state("dynamic_cap_with_penalty")
        communal_pool = norm_state.get("communal_pool_kg", 0)

        assert communal_pool == 5.0, f"Expected pool to remain at 5 kg, got {communal_pool}"

    # ============================================================================
    # R4.7: Monthly Stock Review
    # ============================================================================

    def test_r4_7_monthly_review_at_round_30(self):
        """TC-R4-7: Monthly review occurs every 30 rounds."""
        context = self.create_context(round_number=30, stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)

        norm_state = context.norm_state("dynamic_cap_with_penalty")
        monthly_review = norm_state.get("monthly_review")

        assert monthly_review is not None, "Expected monthly_review to be set"
        assert monthly_review["round"] == 30
        assert monthly_review["stock"] == 150.0
        assert monthly_review["cap_applied"] == 15.0

    def test_r4_7_no_monthly_review_at_other_rounds(self):
        """No monthly review at rounds not divisible by 30."""
        context = self.create_context(round_number=29, stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)

        norm_state = context.norm_state("dynamic_cap_with_penalty")
        monthly_review = norm_state.get("monthly_review")

        assert monthly_review is None or monthly_review.get("round") != 29, \
            "Should not have monthly_review at round 29"

    # ============================================================================
    # R4.8: Excess Return to Lake
    # ============================================================================

    def test_r4_8_excess_returned_to_lake(self):
        """Excess fish above cap is returned to lake."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": 14.0, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        # Stock after harvest: 150 - 14 = 136
        # Stock after return: 136 + 5 = 141
        # Check that override was called (stock_override_kg should be set)
        assert context.stock_override_kg is not None, "Expected stock override to be set"
        # 150 - 14 kept + 5 returned = 141
        expected_stock = 141.0
        assert context.stock_override_kg == expected_stock, \
            f"Expected stock override of {expected_stock}, got {context.stock_override_kg}"

    def test_r4_8_multiple_agents_excess_returned(self):
        """Multiple agents' excess is returned to lake."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)

        # Agent 1: 20 kg catch, 5 kg returned
        decision1 = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.on_agent_settled(context, "agent_1", decision1, decision1.kept_kg)

        # Agent 2: 18 kg catch, 3 kg returned
        decision2 = norm.evaluate(context, "agent_2", raw_kg=18.0, proposed_kg=18.0)
        norm.on_agent_settled(context, "agent_2", decision2, decision2.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": 14.0, "participated": True, "note": None},
            "agent_2": {"effort": 1.0, "harvested_kg": 14.0, "participated": True, "note": None},
        }
        norm.on_round_end(context, round_results)

        # Total returned: 5 + 3 = 8 kg
        # Total kept: 14 + 14 = 28 kg
        # Stock after harvest: 150 - 28 = 122
        # Stock after return: 122 + 8 = 130
        expected_stock = 130.0
        assert context.stock_override_kg == expected_stock, \
            f"Expected stock override of {expected_stock}, got {context.stock_override_kg}"

    # ============================================================================
    # R4.9: Penalty Application Order
    # ============================================================================

    def test_r4_9_penalty_order_correct(self):
        """Penalty application order: reduced limit -> cap -> penalty -> floor."""
        # Agent with reduced personal limit of 10 kg
        context = self.create_context(stock_before=150.0)
        context.runtime["norms"]["dynamic_cap_with_penalty"] = {
            "personal_limits": {"agent_1": {"reduced_limit": 10.0, "set_in_round": 1}},
        }

        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm.on_round_start(context)

        # Agent catches 11 kg with 10 kg personal limit
        decision = norm.evaluate(context, "agent_1", raw_kg=11.0, proposed_kg=11.0)

        # Order: cap (10 kg) -> penalty (1 kg) -> no floor needed
        # Final: 10 - 1 = 9 kg
        assert decision.kept_kg == 9.0, f"Expected 9 kg (10 cap - 1 penalty), got {decision.kept_kg}"
        assert decision.violated is True, "Should be violation (11 > 10)"

    def test_r4_9_penalty_clears_after_trip(self):
        """After any trip (violation or not), penalty should be cleared for next round."""
        # Round 1: Violation, gets penalty for round 2
        context1 = self.create_context(round_number=1, stock_before=150.0)
        norm1 = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm1.on_round_start(context1)
        decision1 = norm1.evaluate(context1, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm1.on_agent_settled(context1, "agent_1", decision1, decision1.kept_kg)

        # Round 2: Compliant trip
        context2 = self.create_context(round_number=2, stock_before=150.0)
        context2.runtime["norms"]["dynamic_cap_with_penalty"] = {
            "personal_limits": {"agent_1": {"reduced_limit": 10.0, "set_in_round": 1}},
            "communal_pool_kg": 1.0,
        }

        norm2 = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm2.on_round_start(context2)
        decision2 = norm2.evaluate(context2, "agent_1", raw_kg=8.0, proposed_kg=8.0)
        norm2.on_agent_settled(context2, "agent_1", decision2, decision2.kept_kg)

        # Penalty should be cleared
        personal_limits = context2.norm_state("dynamic_cap_with_penalty").get("personal_limits", {})
        assert "agent_1" not in personal_limits, "Penalty should clear after trip"

    # ============================================================================
    # R4.10: Agent-Facing Description
    # ============================================================================

    def test_r4_10_description_includes_standard_cap(self):
        """Description includes current standard cap when healthy stock."""
        context = self.create_context(stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "15" in description, "Description should mention 15 kg cap"
        assert "EMERGENCY" not in description, "Should not mention emergency cap"

    def test_r4_10_description_includes_emergency_cap(self):
        """Description includes emergency cap when low stock."""
        context = self.create_context(stock_before=80.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "EMERGENCY CAP ACTIVE" in description, "Should mention emergency cap active"
        assert "10" in description, "Description should mention 10 kg cap"

    def test_r4_10_description_includes_personal_penalty(self):
        """Description includes personal penalty information."""
        context = self.create_context(stock_before=150.0)
        context.runtime["norms"]["dynamic_cap_with_penalty"] = {
            "personal_limits": {"agent_1": {"reduced_limit": 10.0, "set_in_round": 1}},
        }

        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "PENALTY ACTIVE" in description, "Should mention penalty active"
        assert "10" in description, "Should mention reduced limit"

    def test_r4_10_description_includes_communal_pool(self):
        """Description includes communal pool total."""
        context = self.create_context(stock_before=150.0)
        context.runtime["norms"]["dynamic_cap_with_penalty"] = {
            "communal_pool_kg": 5.0,
        }

        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "communal pool" in description.lower(), "Should mention communal pool"
        assert "5.0" in description or "5" in description, "Should mention pool amount"

    def test_r4_10_description_includes_minimum_floor(self):
        """Description includes self-sustenance minimum."""
        context = self.create_context(stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "minimum" in description.lower() or "least 1" in description.lower(), \
            "Should mention minimum floor"

    def test_r4_10_description_includes_violation_penalty(self):
        """Description includes violation penalty information."""
        context = self.create_context(stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "penalty" in description.lower(), "Should mention penalty"
        assert "1" in description, "Should mention 1 kg penalty"

    def test_r4_10_description_includes_logbook(self):
        """Description includes recent logbook entries."""
        context = self.create_context(round_number=3, stock_before=150.0)
        context.runtime["norms"]["dynamic_cap_with_penalty"] = {
            "logbook": [
                {"round": 1, "agent_id": "agent_1", "raw_catch": 20.0, "personal_limit": 15.0,
                 "kept": 14.0, "returned": 5.0, "penalty": 1.0, "violated": True},
                {"round": 2, "agent_id": "agent_1", "raw_catch": 10.0, "personal_limit": 10.0,
                 "kept": 10.0, "returned": 0.0, "penalty": 0.0, "violated": False},
            ]
        }

        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "Round 1" in description or "Round 2" in description, \
            "Should include recent logbook rounds"

    # ============================================================================
    # Edge Cases and Additional Tests
    # ============================================================================

    def test_exactly_at_cap_no_violation(self):
        """Exactly at cap is not a violation."""
        context = self.create_context(stock_before=150.0)
        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=15.0, proposed_kg=15.0)

        assert decision.violated is False, "Exactly at cap should not be violation"
        assert decision.kept_kg == 15.0, f"Expected 15 kg kept, got {decision.kept_kg}"

    def test_emergency_cap_recovery(self):
        """TC-R4-8: Emergency cap recovery when stock increases."""
        # Round 1: Emergency cap
        context1 = self.create_context(round_number=1, stock_before=80.0)
        norm1 = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm1.on_round_start(context1)

        cap1 = context1.norm_state("dynamic_cap_with_penalty").get("current_cap")
        assert cap1 == 10, f"Expected emergency cap 10, got {cap1}"

        # Round 2: Stock recovers, standard cap resumes
        context2 = self.create_context(round_number=2, stock_before=110.0)
        # Copy previous state
        prev_state = context1.norm_state("dynamic_cap_with_penalty")
        context2.runtime["norms"]["dynamic_cap_with_penalty"] = {
            "current_cap": prev_state.get("current_cap"),
            "previous_cap": prev_state.get("current_cap"),
        }

        norm2 = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm2.on_round_start(context2)

        cap2 = context2.norm_state("dynamic_cap_with_penalty").get("current_cap")
        assert cap2 == 15, f"Expected standard cap 15, got {cap2}"

        # Check recovery announcement
        recovery = context2.norm_state("dynamic_cap_with_penalty").get("recovery_announcement")
        assert recovery is True, "Should have recovery announcement"

    def test_multiple_agents_different_penalties(self):
        """TC-R4-10: Multiple agents with different penalty states."""
        context = self.create_context(stock_before=150.0)
        context.runtime["norms"]["dynamic_cap_with_penalty"] = {
            "personal_limits": {
                "agent_2": {"reduced_limit": 10.0, "set_in_round": 1},
                "agent_3": {"reduced_limit": 10.0, "set_in_round": 1},
            },
        }

        norm = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm.on_round_start(context)

        # Agent A: No penalty, standard cap (15 kg)
        decision_a = norm.evaluate(context, "agent_1", raw_kg=16.0, proposed_kg=16.0)
        assert decision_a.violated is True  # 16 > 15
        assert decision_a.kept_kg == 14.0  # 15 - 1

        # Agent B: Pending penalty, personal limit (10 kg)
        decision_b = norm.evaluate(context, "agent_2", raw_kg=12.0, proposed_kg=12.0)
        assert decision_b.violated is True  # 12 > 10
        assert decision_b.kept_kg == 9.0  # 10 - 1

        # Agent C: Pending penalty, catches under limit
        decision_c = norm.evaluate(context, "agent_3", raw_kg=9.0, proposed_kg=9.0)
        assert decision_c.violated is False  # 9 < 10
        assert decision_c.kept_kg == 9.0

    def test_penalty_resets_not_stacks(self):
        """Penalties reset, not stack, when violating while under reduced limit."""
        # Round 1: First violation
        context1 = self.create_context(round_number=1, stock_before=150.0)
        norm1 = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm1.on_round_start(context1)
        decision1 = norm1.evaluate(context1, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm1.on_agent_settled(context1, "agent_1", decision1, decision1.kept_kg)

        # Round 2: Violate again with reduced limit
        context2 = self.create_context(round_number=2, stock_before=150.0)
        context2.runtime["norms"]["dynamic_cap_with_penalty"] = {
            "personal_limits": {"agent_1": {"reduced_limit": 10.0, "set_in_round": 1}},
            "communal_pool_kg": 1.0,
        }

        norm2 = DynamicCapWithPenaltyNorm(key="dynamic_cap_with_penalty", params={})
        norm2.on_round_start(context2)

        # Violate the 10 kg personal limit
        decision2 = norm2.evaluate(context2, "agent_1", raw_kg=12.0, proposed_kg=12.0)
        norm2.on_agent_settled(context2, "agent_1", decision2, decision2.kept_kg)

        # Penalty should reset to 10 kg again (from 15 - 5), not stack to 5 kg
        personal_limits = context2.norm_state("dynamic_cap_with_penalty").get("personal_limits", {})
        assert "agent_1" in personal_limits, "Should still have penalty"
        assert personal_limits["agent_1"]["reduced_limit"] == 10.0, \
            "Penalty should reset to 10 kg, not stack"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
