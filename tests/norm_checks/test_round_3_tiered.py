"""
Independent tests for Round 3 norm implementation: tiered_catch_limit_with_forfeiture

Requirements to verify:
1. Tiered catch limits: high reserves (≥20kg) get min(25% of stock, 30kg),
   low reserves (<20kg) get min(12% of stock, 15kg)
2. Immediate forfeiture of excess catch (returned to lake)
3. One-trip ban for violations
4. Ban lift after ban period expires
5. Transparency of ledger entries via describe()
"""

import pytest
from engine.norms.context import HarvestContext
from engine.norms.engine import NormEngine


def make_test_state(stock_kg=100.0, round_number=1, payoff=None, existing_norm_state=None):
    """Create a minimal state for testing Round 3 norm."""
    runtime = {
        "stock_kg": stock_kg,
        "rounds": [],
        "payoff": payoff or {},
        "dead_agents": [],
        "norms": existing_norm_state or {}
    }

    state = {
        "config": {
            "norms": [
                {
                    "type": "tiered_catch_limit_with_forfeiture",
                    "id": "round_3_limit",
                    "high_reserve_threshold": 20.0,
                    "high_reserve_percent": 0.25,
                    "high_reserve_kg_cap": 30.0,
                    "low_reserve_percent": 0.12,
                    "low_reserve_kg_cap": 15.0,
                    "ban_rounds": 1
                }
            ]
        },
        "fluents": [],
        "runtime": runtime,
        "agents": {
            "agent_0": {"name": "Test Fisher"},
            "agent_1": {"name": "Test Fisher 2"}
        },
        "round_number": round_number
    }
    return state


# ============================================================================
# Requirement 1: Tiered Catch Limits Based on Reserves
# ============================================================================

class TestTieredCatchLimits:
    """Test that tiered catch limits are properly applied based on reserve levels."""

    def test_high_reserves_get_25_percent_limit(self):
        """Fisher with high reserves (>=20kg) gets 25% of stock limit."""
        state = make_test_state(
            stock_kg=100.0,
            payoff={"agent_0": 25.0}  # High reserves
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 25% of 100kg = 25kg limit for high tier
        # 24kg catch should be allowed
        decision = engine.apply(context, "agent_0", 24.0)

        assert decision.kept_kg == 24.0
        assert not decision.violated

    def test_high_reserves_get_30kg_cap(self):
        """Fisher with high reserves is capped at 30kg even if 25% of stock is higher."""
        state = make_test_state(
            stock_kg=200.0,  # 25% = 50kg
            payoff={"agent_0": 25.0}  # High reserves
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 25% of 200kg = 50kg, but cap is 30kg
        # 35kg catch exceeds 30kg cap
        decision = engine.apply(context, "agent_0", 35.0)

        assert decision.violated
        assert decision.kept_kg == 30.0  # Only 30kg kept, 5kg forfeited

    def test_low_reserves_get_12_percent_limit(self):
        """Fisher with low reserves (<20kg) gets 12% of stock limit."""
        state = make_test_state(
            stock_kg=100.0,
            payoff={"agent_0": 15.0}  # Low reserves
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 12% of 100kg = 12kg limit for low tier
        # 11kg catch should be allowed
        decision = engine.apply(context, "agent_0", 11.0)

        assert decision.kept_kg == 11.0
        assert not decision.violated

    def test_low_reserves_get_15kg_cap(self):
        """Fisher with low reserves is capped at 15kg even if 12% of stock is higher."""
        state = make_test_state(
            stock_kg=200.0,  # 12% = 24kg
            payoff={"agent_0": 15.0}  # Low reserves
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 12% of 200kg = 24kg, but cap is 15kg
        # 20kg catch exceeds 15kg cap
        decision = engine.apply(context, "agent_0", 20.0)

        assert decision.violated
        assert decision.kept_kg == 15.0  # Only 15kg kept, 5kg forfeited

    def test_exactly_20kg_is_high_tier(self):
        """Fisher with exactly 20kg reserves is classified as high tier (>= threshold)."""
        state = make_test_state(
            stock_kg=100.0,
            payoff={"agent_0": 20.0}  # Exactly at threshold
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Should get high tier: 25% of 100kg = 25kg limit
        # 24kg catch should be allowed
        decision = engine.apply(context, "agent_0", 24.0)

        assert decision.kept_kg == 24.0
        assert not decision.violated

    def test_just_below_20kg_is_low_tier(self):
        """Fisher with just under 20kg reserves is classified as low tier."""
        state = make_test_state(
            stock_kg=100.0,
            payoff={"agent_0": 19.9}  # Just below threshold
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Should get low tier: 12% of 100kg = 12kg limit
        # 15kg catch exceeds 12kg limit
        decision = engine.apply(context, "agent_0", 15.0)

        assert decision.violated
        assert decision.kept_kg == 12.0  # Only 12kg kept, 3kg forfeited


# ============================================================================
# Requirement 2: Immediate Forfeiture of Excess
# ============================================================================

class TestImmediateForfeiture:
    """Test that excess catch is immediately forfeited and returned to lake."""

    def test_excess_is_forfeited_immediately_high_tier(self):
        """Excess above high tier limit is forfeited immediately."""
        state = make_test_state(
            stock_kg=100.0,
            payoff={"agent_0": 25.0}  # High reserves
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 25% of 100kg = 25kg limit
        # 30kg catch means 5kg excess
        decision = engine.apply(context, "agent_0", 30.0)

        assert decision.violated
        assert decision.kept_kg == 25.0  # Only limit kept
        assert "5.0kg" in decision.note or "excess" in decision.note.lower()

    def test_excess_is_forfeited_immediately_low_tier(self):
        """Excess above low tier limit is forfeited immediately."""
        state = make_test_state(
            stock_kg=100.0,
            payoff={"agent_0": 15.0}  # Low reserves
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 12% of 100kg = 12kg limit
        # 18kg catch means 6kg excess
        decision = engine.apply(context, "agent_0", 18.0)

        assert decision.violated
        assert decision.kept_kg == 12.0  # Only limit kept
        assert "6.0kg" in decision.note or "excess" in decision.note.lower()

    def test_excess_returned_to_stock_on_round_end(self):
        """Forfeited excess is added back to stock at round end."""
        state = make_test_state(
            stock_kg=100.0,
            payoff={"agent_0": 25.0}  # High reserves
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Violation: 30kg catch, 25kg limit, 5kg excess
        decision = engine.apply(context, "agent_0", 30.0)

        # Simulate stock_after_regrowth (normally computed by harvest action)
        stock_after_regrowth = 80.0
        context.override_stock_after_regrowth(stock_after_regrowth)

        # End round - excess should be added back to stock
        round_results = {
            "agent_0": {
                "effort": 1.0,
                "harvested_kg": decision.kept_kg,
                "participated": True,
                "note": decision.note
            }
        }
        engine.end_round(context, round_results)

        # Stock should be increased by excess amount
        # 80.0 + 5.0 (excess) = 85.0
        expected_stock = stock_after_regrowth + 5.0
        assert context.stock_override_kg == expected_stock


# ============================================================================
# Requirement 3 & 4: Ban for Violations and Ban Lift
# ============================================================================

class TestBanMechanism:
    """Test that violations result in one-trip bans that expire properly."""

    def test_violation_records_ban(self):
        """A violation should record a ban for the next round."""
        state = make_test_state(
            stock_kg=100.0,
            round_number=5,
            payoff={"agent_0": 25.0}
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Violation in round 5
        decision = engine.apply(context, "agent_0", 30.0)

        assert decision.violated

        # Check that ban was recorded in norm state
        norm_state = context.norm_state("round_3_limit")
        assert "agent_0" in norm_state.get("ban_until", {})
        assert norm_state["ban_until"]["agent_0"] == 7  # Banned until after round 6

    def test_banned_agent_is_ineligible(self):
        """A banned agent should be ineligible to fish during ban period."""
        # Pre-set a ban from a previous violation
        existing_norm_state = {
            "round_3_limit": {
                "violations": {"agent_0": 4},
                "ban_until": {"agent_0": 6}  # Banned until after round 5
            }
        }

        state = make_test_state(
            stock_kg=100.0,
            round_number=5,  # During ban period
            payoff={"agent_0": 25.0},
            existing_norm_state=existing_norm_state
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])

        norm = engine.norms[0]
        is_eligible = norm.is_eligible(context, "agent_0")

        assert not is_eligible

    def test_ban_expires_after_period(self):
        """A ban should expire after the ban period."""
        # Pre-set a ban that should have expired
        existing_norm_state = {
            "round_3_limit": {
                "violations": {"agent_0": 4},
                "ban_until": {"agent_0": 6}  # Banned until after round 5
            }
        }

        state = make_test_state(
            stock_kg=100.0,
            round_number=7,  # After ban period
            payoff={"agent_0": 25.0},
            existing_norm_state=existing_norm_state
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])

        norm = engine.norms[0]
        is_eligible = norm.is_eligible(context, "agent_0")

        assert is_eligible

    def test_describe_shows_ban_status(self):
        """The describe method should indicate when a fisher is banned."""
        existing_norm_state = {
            "round_3_limit": {
                "ban_until": {"agent_0": 6}
            }
        }

        state = make_test_state(
            stock_kg=100.0,
            round_number=5,
            payoff={"agent_0": 25.0},
            existing_norm_state=existing_norm_state
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])

        norm = engine.norms[0]
        description = norm.describe(context, "agent_0")

        assert "banned" in description.lower()


# ============================================================================
# Requirement 5: Transparency via describe()
# ============================================================================

class TestTransparency:
    """Test that describe() provides comprehensive information."""

    def test_describe_shows_high_tier_info(self):
        """Describe should show high tier classification and limit for high reserves."""
        state = make_test_state(
            stock_kg=100.0,
            payoff={"agent_0": 25.0}  # High reserves
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])

        norm = engine.norms[0]
        description = norm.describe(context, "agent_0")

        assert "25.0kg" in description  # Current reserves
        assert "high" in description.lower()  # High tier
        assert "25%" in description  # 25% limit
        assert "30kg" in description or "30" in description  # 30kg cap
        assert "25.0kg" in description or "limit" in description.lower()  # Effective limit

    def test_describe_shows_low_tier_info(self):
        """Describe should show low tier classification and limit for low reserves."""
        state = make_test_state(
            stock_kg=100.0,
            payoff={"agent_0": 15.0}  # Low reserves
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])

        norm = engine.norms[0]
        description = norm.describe(context, "agent_0")

        assert "15.0kg" in description  # Current reserves
        assert "low" in description.lower()  # Low tier
        assert "12%" in description  # 12% limit
        assert "15kg" in description or "15" in description  # 15kg cap
        assert "12.0kg" in description or "limit" in description.lower()  # Effective limit

    def test_describe_shows_lake_stock(self):
        """Describe should show current lake stock."""
        state = make_test_state(
            stock_kg=150.0,
            payoff={"agent_0": 25.0}
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])

        norm = engine.norms[0]
        description = norm.describe(context, "agent_0")

        assert "150.0kg" in description or "stock" in description.lower()


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_reserves_is_low_tier(self):
        """Fisher with zero reserves should be low tier."""
        state = make_test_state(
            stock_kg=100.0,
            payoff={"agent_0": 0.0}
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 12% of 100kg = 12kg limit for low tier
        decision = engine.apply(context, "agent_0", 15.0)

        assert decision.violated
        assert decision.kept_kg == 12.0

    def test_high_reserves_with_low_stock(self):
        """High tier fisher with very low stock - 25% might be lower than 12% cap of low tier."""
        state = make_test_state(
            stock_kg=40.0,  # Very low stock
            payoff={"agent_0": 25.0}  # High reserves
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 25% of 40kg = 10kg limit for high tier
        # 15kg catch should trigger violation
        decision = engine.apply(context, "agent_0", 15.0)

        assert decision.violated
        assert decision.kept_kg == 10.0  # Only 10kg kept (25% of 40kg)

    def test_exactly_at_limit_no_violation(self):
        """Catch exactly at the limit should not trigger violation."""
        state = make_test_state(
            stock_kg=100.0,
            payoff={"agent_0": 25.0}  # High reserves
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Exactly 25kg (25% of 100kg)
        decision = engine.apply(context, "agent_0", 25.0)

        assert not decision.violated
        assert decision.kept_kg == 25.0

    def test_multiple_agents_different_tiers(self):
        """Multiple agents can be in different tiers simultaneously."""
        state = make_test_state(
            stock_kg=100.0,
            payoff={"agent_0": 25.0, "agent_1": 15.0}  # Different tiers
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # agent_0 (high tier): 25% of 100 = 25kg limit
        decision_0 = engine.apply(context, "agent_0", 24.0)
        assert not decision_0.violated
        assert decision_0.kept_kg == 24.0

        # agent_1 (low tier): 12% of 100 = 12kg limit
        decision_1 = engine.apply(context, "agent_1", 11.0)
        assert not decision_1.violated
        assert decision_1.kept_kg == 11.0

    def test_violation_message_includes_tier(self):
        """Violation message should indicate which tier was applied."""
        state = make_test_state(
            stock_kg=100.0,
            payoff={"agent_0": 25.0}  # High reserves
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        decision = engine.apply(context, "agent_0", 30.0)

        assert decision.violated
        # Should mention "high tier" or similar
        assert "high" in decision.note.lower() or "tier" in decision.note.lower()
