"""
Independent evaluator tests for Round 1 norm implementation.

These tests verify the requirements from state/norm_specs/round_1.md:
1. Catch limit enforcement (15% or 20kg, whichever is less)
2. Ban eligibility check
3. Forfeited fish added back to stock

Author: norm-evaluator (independent verification)
"""

import pytest
from engine.norms.context import HarvestContext
from engine.norms.engine import NormEngine
from norms.catch_limit_with_forfeiture import CatchLimitWithForfeitureNorm


def make_test_context(stock_kg=100.0, round_number=1, existing_bans=None, existing_norm_state=None):
    """Create a minimal state for testing."""
    state = {
        "config": {
            "norms": [
                {
                    "type": "catch_limit_with_forfeiture",
                    "id": "test_limit",
                    "percent_limit": 0.15,
                    "kg_limit": 20.0,
                    "ban_days": 1
                }
            ]
        },
        "fluents": [],
        "runtime": {
            "stock_kg": stock_kg,
            "rounds": [],
            "payoff": {},
            "dead_agents": [],
            "norms": {}
        },
        "agents": {
            "agent_0": {"name": "Test Fisher"},
            "agent_1": {"name": "Test Fisher 2"},
        },
        "round_number": round_number
    }

    if existing_bans:
        state["runtime"]["norms"]["test_limit"] = {"bans": existing_bans.copy()}
    elif existing_norm_state:
        state["runtime"]["norms"]["test_limit"] = existing_norm_state.copy()

    return HarvestContext.from_state(state)


class TestRequirement1_CatchLimitEnforcement:
    """
    Requirement 1: Catch Limit Enforcement (15% or 20kg)
    
    The norm must enforce a catch limit of min(15% of current stock, 20kg).
    Any actual haul exceeding this limit has the excess marked as "forfeited".
    """

    def test_limit_calculation_15_percent_binding(self):
        """When 15% of stock < 20kg, limit should be 15% of stock."""
        # Stock 100, 15% = 15kg, which is less than 20kg
        context = make_test_context(stock_kg=100.0, round_number=1)
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        # Start round to initialize scratch
        norm.on_round_start(context)
        
        # 25kg catch, limit should be 15kg (15% of 100)
        decision = norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)
        
        assert decision.kept_kg == 15.0, f"Expected kept_kg=15.0 (15% of 100), got {decision.kept_kg}"
        assert decision.violated is True
        assert "15" in decision.note or "15.0" in decision.note

    def test_limit_calculation_20kg_binding(self):
        """When 20kg < 15% of stock, limit should be 20kg."""
        # Stock 200, 15% = 30kg, which is more than 20kg
        context = make_test_context(stock_kg=200.0, round_number=1)
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        norm.on_round_start(context)
        
        # 25kg catch, limit should be 20kg
        decision = norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)
        
        assert decision.kept_kg == 20.0, f"Expected kept_kg=20.0, got {decision.kept_kg}"
        assert decision.violated is True

    def test_exactly_at_15_percent_limit_no_violation(self):
        """Catch exactly at 15% limit should not trigger violation."""
        context = make_test_context(stock_kg=100.0, round_number=1)
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        norm.on_round_start(context)
        
        # Exactly 15kg catch (15% of 100)
        decision = norm.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=15.0)
        
        assert decision.kept_kg == 15.0
        assert decision.violated is False, "Exactly at limit should not be a violation"
        assert decision.sanction is None

    def test_exactly_at_20kg_limit_no_violation(self):
        """Catch exactly at 20kg limit should not trigger violation."""
        context = make_test_context(stock_kg=200.0, round_number=1)
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        norm.on_round_start(context)
        
        # Exactly 20kg catch
        decision = norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=20.0)
        
        assert decision.kept_kg == 20.0
        assert decision.violated is False, "Exactly at limit should not be a violation"

    def test_limit_uses_departure_stock_level(self):
        """The 15% limit is applied using the stock level at the moment of departure."""
        # This is implicit in the implementation since stock_before is captured
        # at context creation time (start of round)
        context = make_test_context(stock_kg=100.0, round_number=1)
        
        # Verify stock_before is set correctly
        assert context.stock_before == 100.0
        
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=20.0)
        
        # Limit should be based on stock_before (100kg), not any changed value
        # 15% of 100 = 15kg, so 20kg catch should be capped to 15kg
        assert decision.kept_kg == 15.0

    def test_violation_includes_correct_forfeiture_amount(self):
        """Violation note should include correct forfeiture amount."""
        context = make_test_context(stock_kg=100.0, round_number=1)
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        norm.on_round_start(context)
        
        # 25kg catch, 15kg limit, 10kg forfeited
        decision = norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)
        
        assert decision.violated is True
        assert "10" in decision.note, f"Note should mention 10kg forfeited: {decision.note}"
        assert "forfeited" in decision.note.lower()


class TestRequirement2_BanEligibilityCheck:
    """
    Requirement 2: Ban Eligibility Check
    
    Banned fishers should be ineligible to fish during their ban period.
    The dock officer denies permission to launch to any fisher whose 
    ban_until date is still in the future.
    """

    def test_banned_fisher_is_ineligible(self):
        """Fisher with active ban should be ineligible."""
        # Agent banned until round 6, currently round 5
        context = make_test_context(
            stock_kg=100.0, 
            round_number=5, 
            existing_bans={"agent_0": 6}
        )
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        is_eligible = norm.is_eligible(context, "agent_0")
        
        assert is_eligible is False, "Fisher with ban_until=6 should be ineligible at round 5"

    def test_fisher_with_expired_ban_is_eligible(self):
        """Fisher whose ban has expired should be eligible."""
        # Agent banned until round 5, currently round 6
        context = make_test_context(
            stock_kg=100.0, 
            round_number=6, 
            existing_bans={"agent_0": 5}
        )
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        is_eligible = norm.is_eligible(context, "agent_0")
        
        assert is_eligible is True, "Fisher with ban_until=5 should be eligible at round 6"

    def test_fisher_at_exact_ban_until_is_eligible(self):
        """Fisher at exact ban_until round should be eligible (ban is up to but not including)."""
        # Agent banned until round 5, currently round 5
        context = make_test_context(
            stock_kg=100.0, 
            round_number=5, 
            existing_bans={"agent_0": 5}
        )
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        is_eligible = norm.is_eligible(context, "agent_0")
        
        assert is_eligible is True, "Fisher with ban_until=5 should be eligible at round 5"

    def test_violation_creates_one_day_ban(self):
        """Violating the catch limit should result in a one-day ban."""
        context = make_test_context(stock_kg=100.0, round_number=5)
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        norm.on_round_start(context)
        
        # Trigger violation at round 5
        decision = norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)
        
        assert decision.violated is True
        
        # Check ban was recorded: ban_until should be round 6 (current + 1)
        norm_state = context.norm_state("test_limit")
        assert "bans" in norm_state
        assert "agent_0" in norm_state["bans"]
        assert norm_state["bans"]["agent_0"] == 6, "Ban should be for 1 day (round 6)"

    def test_ban_is_recorded_in_ledger(self):
        """Ban should be recorded in the norm state (ledger)."""
        context = make_test_context(stock_kg=100.0, round_number=1)
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        norm.on_round_start(context)
        norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)
        
        # Verify the ledger (norm_state) has the ban
        norm_state = context.norm_state("test_limit")
        assert "bans" in norm_state
        assert norm_state["bans"]["agent_0"] == 2

    def test_description_shows_ban_status(self):
        """The describe() method should inform banned fishers of their status."""
        context = make_test_context(
            stock_kg=100.0, 
            round_number=5, 
            existing_bans={"agent_0": 8}  # Banned for 3 more rounds
        )
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        description = norm.describe(context, "agent_0")
        
        assert "banned" in description.lower()
        assert "3" in description, "Should indicate 3 rounds remaining"

    def test_multiple_fishers_can_have_different_ban_status(self):
        """Different fishers can have different ban statuses."""
        context = make_test_context(
            stock_kg=100.0, 
            round_number=5, 
            existing_bans={"agent_0": 6, "agent_1": 4}  # agent_0 banned, agent_1 not
        )
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        agent_0_eligible = norm.is_eligible(context, "agent_0")
        agent_1_eligible = norm.is_eligible(context, "agent_1")
        
        assert agent_0_eligible is False, "agent_0 should be ineligible (banned until 6)"
        assert agent_1_eligible is True, "agent_1 should be eligible (ban expired at 4)"


class TestRequirement3_ForfeitedFishReturnedToStock:
    """
    Requirement 3: Forfeited Fish Added Back to Stock
    
    Forfeited fish must be returned to the communal pool (lake stock).
    The chair opens the ledger each night to update the lake's stock:
    new stock = previous stock + any forfeited fish.
    """

    def test_forfeiture_tracked_per_agent(self):
        """Forfeited amounts should be tracked per agent for the round."""
        context = make_test_context(stock_kg=100.0, round_number=1)
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        norm.on_round_start(context)
        
        # Agent violates: 25kg catch, 15kg limit, 10kg forfeited
        norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)
        
        # Check scratch pad has forfeiture
        scratch = context.round_scratch("test_limit")
        assert "forfeited_this_round" in scratch
        assert scratch["forfeited_this_round"]["agent_0"] == 10.0

    def test_forfeited_fish_added_to_stock(self):
        """On round end, forfeited fish should be added back to stock."""
        context = make_test_context(stock_kg=100.0, round_number=1)
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        norm.on_round_start(context)
        
        # Trigger forfeiture
        decision = norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)
        
        # Simulate what harvest action does - set stock after regrowth
        stock_after_regrowth = 80.0  # Simulated
        context.override_stock_after_regrowth(stock_after_regrowth)
        
        # Call on_round_end
        round_results = {
            "agent_0": {
                "effort": 1.0,
                "harvested_kg": decision.kept_kg,
                "participated": True,
                "note": decision.note
            }
        }
        norm.on_round_end(context, round_results)
        
        # Stock should be increased by forfeited amount (10kg)
        expected_stock = stock_after_regrowth + 10.0
        assert context.stock_override_kg == expected_stock, \
            f"Expected stock {expected_stock}, got {context.stock_override_kg}"

    def test_multiple_forfeitures_summed(self):
        """Multiple forfeitures in one round should be summed."""
        context = make_test_context(stock_kg=100.0, round_number=1)
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        norm.on_round_start(context)
        
        # Both agents violate
        # agent_0: 25kg catch, 15kg limit, 10kg forfeited
        decision_0 = norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)
        # agent_1: 30kg catch, 15kg limit, 15kg forfeited
        decision_1 = norm.evaluate(context, "agent_1", raw_kg=30.0, proposed_kg=30.0)
        
        # Check scratch pad
        scratch = context.round_scratch("test_limit")
        assert scratch["forfeited_this_round"]["agent_0"] == 10.0
        assert scratch["forfeited_this_round"]["agent_1"] == 15.0
        
        # Simulate round end
        stock_after_regrowth = 60.0
        context.override_stock_after_regrowth(stock_after_regrowth)
        
        round_results = {
            "agent_0": {
                "effort": 1.0,
                "harvested_kg": decision_0.kept_kg,
                "participated": True,
                "note": decision_0.note
            },
            "agent_1": {
                "effort": 1.0,
                "harvested_kg": decision_1.kept_kg,
                "participated": True,
                "note": decision_1.note
            }
        }
        norm.on_round_end(context, round_results)
        
        # Total forfeited = 10 + 15 = 25kg
        expected_stock = stock_after_regrowth + 25.0
        assert context.stock_override_kg == expected_stock

    def test_no_forfeiture_when_no_violations(self):
        """When there are no violations, stock should not change."""
        context = make_test_context(stock_kg=100.0, round_number=1)
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        norm.on_round_start(context)
        
        # No violations - within limit
        decision = norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
        
        stock_after_regrowth = 90.0
        context.override_stock_after_regrowth(stock_after_regrowth)
        
        round_results = {
            "agent_0": {
                "effort": 0.5,
                "harvested_kg": decision.kept_kg,
                "participated": True,
                "note": decision.note
            }
        }
        norm.on_round_end(context, round_results)
        
        # Stock should remain unchanged (no forfeiture)
        assert context.stock_override_kg == stock_after_regrowth


class TestIntegration_WithNormEngine:
    """Integration tests using the full NormEngine."""

    def test_full_engine_violation_flow(self):
        """Test complete flow through NormEngine."""
        context = make_test_context(stock_kg=100.0, round_number=1)
        engine = NormEngine.from_config(context.config)
        
        engine.start_round(context)
        
        # Agent violates
        decision = engine.apply(context, "agent_0", raw_kg=25.0)
        
        assert decision.kept_kg == 15.0
        assert decision.violated is True
        
        # Finish round
        round_results = {
            "agent_0": {
                "effort": 1.0,
                "harvested_kg": decision.kept_kg,
                "participated": True,
                "note": decision.note
            }
        }
        
        context.override_stock_after_regrowth(80.0)
        engine.end_round(context, round_results)
        
        # Verify stock updated
        assert context.stock_override_kg == 90.0  # 80 + 10 forfeited
        
        # Verify ban recorded
        norm_state = context.norm_state("test_limit")
        assert norm_state["bans"]["agent_0"] == 2

    def test_engine_eligibility_integration(self):
        """Test that engine correctly checks eligibility."""
        context = make_test_context(
            stock_kg=100.0, 
            round_number=5, 
            existing_bans={"agent_0": 6}
        )
        engine = NormEngine.from_config(context.config)
        engine.start_round(context)
        
        # Should be ineligible
        assert engine.is_eligible(context, "agent_0") is False
        
        # Description should note ban
        note = engine.ineligibility_note(context, "agent_0")
        assert "banned" in note.lower()


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_very_small_stock(self):
        """Test behavior with very small stock."""
        # Stock 10, 15% = 1.5kg
        context = make_test_context(stock_kg=10.0, round_number=1)
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)
        
        # Limit is min(1.5, 20) = 1.5kg
        assert decision.kept_kg == 1.5
        assert decision.violated is True

    def test_zero_catch(self):
        """Test behavior with zero catch."""
        context = make_test_context(stock_kg=100.0, round_number=1)
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_0", raw_kg=0.0, proposed_kg=0.0)
        
        assert decision.kept_kg == 0.0
        assert decision.violated is False

    def test_ban_persists_across_rounds(self):
        """Test that bans persist in norm state across round boundaries."""
        # Round 1: Agent gets banned
        context1 = make_test_context(stock_kg=100.0, round_number=1)
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        norm.on_round_start(context1)
        norm.evaluate(context1, "agent_0", raw_kg=25.0, proposed_kg=25.0)
        
        # Get the norm state that would be saved
        norm_state = context1.norm_state("test_limit")
        
        # Round 2: New context but with saved norm state
        context2 = make_test_context(stock_kg=100.0, round_number=2)
        # Copy the ban state from round 1
        context2.runtime["norms"]["test_limit"] = {"bans": norm_state["bans"].copy()}
        
        norm2 = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 1
        })
        
        # At round 2, ban_until=2, so should be eligible now
        assert norm2.is_eligible(context2, "agent_0") is True

    def test_custom_ban_days_parameter(self):
        """Test that ban_days parameter is respected."""
        context = make_test_context(stock_kg=100.0, round_number=5)
        norm = CatchLimitWithForfeitureNorm(key="test_limit", params={
            "percent_limit": 0.15,
            "kg_limit": 20.0,
            "ban_days": 3  # 3 day ban
        })
        
        norm.on_round_start(context)
        norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)
        
        norm_state = context.norm_state("test_limit")
        # ban_until should be current_round (5) + ban_days (3) = 8
        assert norm_state["bans"]["agent_0"] == 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
