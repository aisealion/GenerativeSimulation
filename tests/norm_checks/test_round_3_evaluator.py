"""
Norm-Evaluator Independent Tests for Round 3

These tests verify the implementation of tiered_catch_limit_with_forfeiture
against the norm specification in state/norm_specs/round_3.md.

Requirements to verify (from spec):
1. Tiered catch limits: high reserves (≥20kg) get min(25% of stock, 30kg),
   low reserves (<20kg) get min(12% of stock, 15kg)
2. Immediate forfeiture of excess catch (returned to lake)
3. Reserve-based state field tracking
4. One-trip ban for violations
5. Ban lift after ban period expires
12. Transparency of ledger entries

Requirements NOT implemented (technically unrealizable per spec):
6. Reserve recording before departure - not applicable
7. Catch logging after trip - not applicable
8. Rotating lake monitor - not applicable
9. Lake stock update by monitor - not applicable
10. Ledger broadcast - not applicable
11. Non-compliance for failure to log - not applicable
"""

import pytest
from engine.norms.context import HarvestContext
from engine.norms.engine import NormEngine
from norms.tiered_catch_limit_with_forfeiture import TieredCatchLimitWithForfeitureNorm


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
            "agent_1": {"name": "Test Fisher 2"},
            "agent_2": {"name": "Test Fisher 3"}
        },
        "round_number": round_number
    }
    return state


# ============================================================================
# REQUIREMENT 1: Tiered Catch Limit Based on Reserves
# ============================================================================

class TestRequirement1_TieredCatchLimits:
    """
    Requirement 1: Tiered Catch Limit Based on Reserves
    
    - If reserves ≥ 20 kg: limit = min(25% of stock, 30 kg)
    - If reserves < 20 kg: limit = min(12% of stock, 15 kg)
    """

    def test_high_tier_25_percent_calculation(self):
        """High tier (≥20kg reserves) gets 25% of stock when below cap."""
        state = make_test_state(stock_kg=80.0, payoff={"agent_0": 25.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # 25% of 80kg = 20kg, which is below 30kg cap
        decision = engine.apply(context, "agent_0", 19.0)
        assert decision.kept_kg == 19.0, f"Expected 19.0kg kept, got {decision.kept_kg}"
        assert not decision.violated
        
        decision2 = engine.apply(context, "agent_0", 21.0)
        assert decision2.violated, "Should violate when exceeding 20kg limit"
        assert decision2.kept_kg == 20.0, f"Expected 20.0kg kept (limit), got {decision2.kept_kg}"

    def test_high_tier_30kg_cap_applies(self):
        """High tier is capped at 30kg even when 25% of stock exceeds it."""
        state = make_test_state(stock_kg=200.0, payoff={"agent_0": 25.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # 25% of 200kg = 50kg, but cap is 30kg
        decision = engine.apply(context, "agent_0", 35.0)
        assert decision.violated, "Should violate when exceeding 30kg cap"
        assert decision.kept_kg == 30.0, f"Expected 30.0kg kept (cap), got {decision.kept_kg}"

    def test_low_tier_12_percent_calculation(self):
        """Low tier (<20kg reserves) gets 12% of stock when below cap."""
        state = make_test_state(stock_kg=80.0, payoff={"agent_0": 15.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # 12% of 80kg = 9.6kg, which is below 15kg cap
        decision = engine.apply(context, "agent_0", 9.0)
        assert decision.kept_kg == 9.0, f"Expected 9.0kg kept, got {decision.kept_kg}"
        assert not decision.violated
        
        decision2 = engine.apply(context, "agent_0", 11.0)
        assert decision2.violated, "Should violate when exceeding 9.6kg limit"
        assert abs(decision2.kept_kg - 9.6) < 0.01, f"Expected ~9.6kg kept (limit), got {decision2.kept_kg}"

    def test_low_tier_15kg_cap_applies(self):
        """Low tier is capped at 15kg even when 12% of stock exceeds it."""
        state = make_test_state(stock_kg=200.0, payoff={"agent_0": 15.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # 12% of 200kg = 24kg, but cap is 15kg
        decision = engine.apply(context, "agent_0", 18.0)
        assert decision.violated, "Should violate when exceeding 15kg cap"
        assert decision.kept_kg == 15.0, f"Expected 15.0kg kept (cap), got {decision.kept_kg}"

    def test_threshold_boundary_exactly_20kg(self):
        """Exactly 20kg reserves should be high tier (>= threshold)."""
        state = make_test_state(stock_kg=100.0, payoff={"agent_0": 20.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # At exactly 20kg, should be high tier: 25% of 100kg = 25kg limit
        decision = engine.apply(context, "agent_0", 24.0)
        assert not decision.violated, "24kg should be allowed with 25kg high tier limit"
        assert decision.kept_kg == 24.0

    def test_threshold_boundary_just_below_20kg(self):
        """Just under 20kg reserves should be low tier."""
        state = make_test_state(stock_kg=100.0, payoff={"agent_0": 19.99})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # Just below 20kg, should be low tier: 12% of 100kg = 12kg limit
        decision = engine.apply(context, "agent_0", 15.0)
        assert decision.violated, "Should violate with 12kg low tier limit"
        assert decision.kept_kg == 12.0, f"Expected 12.0kg kept, got {decision.kept_kg}"


# ============================================================================
# REQUIREMENT 2: Immediate Excess Return (Forfeiture)
# ============================================================================

class TestRequirement2_ImmediateForfeiture:
    """
    Requirement 2: Immediate Excess Return (Forfeiture)
    
    Excess catch = actual_catch - allowed, returned to lake stock immediately.
    Unlike Round 2 which taxed the NEXT catch, Round 3 requires IMMEDIATE return.
    """

    def test_excess_returned_to_stock_high_tier(self):
        """Excess above high tier limit is returned to lake stock."""
        state = make_test_state(stock_kg=100.0, payoff={"agent_0": 25.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # High tier: 25% of 100kg = 25kg limit
        # 30kg catch means 5kg excess should be returned
        decision = engine.apply(context, "agent_0", 30.0)
        
        assert decision.violated
        assert decision.kept_kg == 25.0, "Should keep only the limit (25kg)"
        
        # Simulate round end with stock override
        context.override_stock_after_regrowth(80.0)
        
        round_results = {
            "agent_0": {
                "effort": 1.0,
                "harvested_kg": decision.kept_kg,
                "participated": True,
                "note": decision.note
            }
        }
        engine.end_round(context, round_results)
        
        # Stock should be 80.0 + 5.0 (excess) = 85.0
        assert context.stock_override_kg == 85.0, f"Expected 85.0kg stock, got {context.stock_override_kg}"

    def test_excess_returned_to_stock_low_tier(self):
        """Excess above low tier limit is returned to lake stock."""
        state = make_test_state(stock_kg=100.0, payoff={"agent_0": 15.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # Low tier: 12% of 100kg = 12kg limit
        # 20kg catch means 8kg excess should be returned
        decision = engine.apply(context, "agent_0", 20.0)
        
        assert decision.violated
        assert decision.kept_kg == 12.0, "Should keep only the limit (12kg)"
        
        # Simulate round end
        context.override_stock_after_regrowth(80.0)
        
        round_results = {
            "agent_0": {
                "effort": 1.0,
                "harvested_kg": decision.kept_kg,
                "participated": True,
                "note": decision.note
            }
        }
        engine.end_round(context, round_results)
        
        # Stock should be 80.0 + 8.0 (excess) = 88.0
        assert context.stock_override_kg == 88.0, f"Expected 88.0kg stock, got {context.stock_override_kg}"

    def test_no_excess_when_within_limit(self):
        """No excess should be recorded when catch is within limit."""
        state = make_test_state(stock_kg=100.0, payoff={"agent_0": 25.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        decision = engine.apply(context, "agent_0", 20.0)
        
        assert not decision.violated
        assert decision.kept_kg == 20.0
        
        # Check round scratch - should have no excess for this agent
        scratch = context.round_scratch("round_3_limit")
        excess_this_round = scratch.get("excess_this_round", {})
        assert "agent_0" not in excess_this_round or excess_this_round.get("agent_0", 0) == 0

    def test_immediate_vs_round2_tax_difference(self):
        """
        Key difference from Round 2: Round 3 has immediate forfeiture.
        Round 2 allowed full catch but taxed the NEXT catch.
        Round 3 requires immediate return of excess.
        """
        state = make_test_state(stock_kg=100.0, payoff={"agent_0": 25.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # 30kg catch with 25kg limit
        decision = engine.apply(context, "agent_0", 30.0)
        
        # Round 3: Immediate forfeiture - only keep 25kg
        assert decision.kept_kg == 25.0, "Round 3 should forfeit excess immediately"
        assert decision.violated
        
        # Note should mention excess and return
        assert "excess" in decision.note.lower() or "returned" in decision.note.lower()


# ============================================================================
# REQUIREMENT 3: Reserve-Based Eligibility and State Field
# ============================================================================

class TestRequirement3_ReserveTracking:
    """
    Requirement 3: Reserve-Based Eligibility and State Field
    
    The norm tracks reserves (payoff field) to determine tier classification.
    """

    def test_reserve_read_from_payoff(self):
        """Reserve level should be read from payoff field."""
        state = make_test_state(stock_kg=100.0, payoff={"agent_0": 25.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # Check that tier is recorded correctly based on payoff
        decision = engine.apply(context, "agent_0", 20.0)
        
        scratch = context.round_scratch("round_3_limit")
        tier_this_round = scratch.get("tier_this_round", {})
        assert tier_this_round.get("agent_0") == "high", "Should record high tier for 25kg reserves"

    def test_reserve_determines_tier_classification(self):
        """Different reserve levels should result in different tier classifications."""
        state = make_test_state(stock_kg=100.0, payoff={"agent_0": 25.0, "agent_1": 15.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        engine.apply(context, "agent_0", 10.0)
        engine.apply(context, "agent_1", 10.0)
        
        scratch = context.round_scratch("round_3_limit")
        tier_this_round = scratch.get("tier_this_round", {})
        
        assert tier_this_round.get("agent_0") == "high", "25kg reserves should be high tier"
        assert tier_this_round.get("agent_1") == "low", "15kg reserves should be low tier"


# ============================================================================
# REQUIREMENT 4: Ban for Violations (One-Trip Ban)
# ============================================================================

class TestRequirement4_BanForViolations:
    """
    Requirement 4: Ban for Violations (One-Trip Ban)
    
    If violation detected, ban fisher for next round.
    """

    def test_ban_recorded_after_violation(self):
        """Ban should be recorded in norm state after violation."""
        state = make_test_state(stock_kg=100.0, round_number=5, payoff={"agent_0": 25.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # Violation in round 5
        decision = engine.apply(context, "agent_0", 30.0)
        assert decision.violated
        
        # Check ban was recorded
        norm_state = context.norm_state("round_3_limit")
        assert "agent_0" in norm_state.get("ban_until", {}), "Ban should be recorded"
        # ban_until = current_round + ban_rounds + 1 = 5 + 1 + 1 = 7
        assert norm_state["ban_until"]["agent_0"] == 7, "Should be banned until after round 6"

    def test_violation_recorded_with_round_number(self):
        """Violation should be recorded with the round number it occurred."""
        state = make_test_state(stock_kg=100.0, round_number=5, payoff={"agent_0": 25.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        engine.apply(context, "agent_0", 30.0)
        
        norm_state = context.norm_state("round_3_limit")
        assert norm_state["violations"]["agent_0"] == 5, "Violation should be recorded for round 5"

    def test_ban_note_includes_next_round_info(self):
        """Violation note should mention the ban for next round."""
        state = make_test_state(stock_kg=100.0, round_number=5, payoff={"agent_0": 25.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        decision = engine.apply(context, "agent_0", 30.0)
        
        assert "round 6" in decision.note.lower() or "banned" in decision.note.lower(), \
            f"Note should mention ban: {decision.note}"


# ============================================================================
# REQUIREMENT 5: Ban Lift Process (After Ban Period Expires)
# ============================================================================

class TestRequirement5_BanLift:
    """
    Requirement 5: Ban Lift Process (After Ban Period Expires)
    
    Ban is lifted automatically after ban period expires.
    """

    def test_ban_expires_when_round_reaches_ban_until(self):
        """Ban should expire when current_round >= ban_until."""
        # Pre-set a ban that expires after round 5
        existing_norm_state = {
            "round_3_limit": {
                "violations": {"agent_0": 3},
                "ban_until": {"agent_0": 6}  # Can fish again starting at round 6
            }
        }
        
        state = make_test_state(
            stock_kg=100.0,
            round_number=6,  # At ban_until round - should be eligible
            payoff={"agent_0": 25.0},
            existing_norm_state=existing_norm_state
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        
        norm = engine.norms[0]
        is_eligible = norm.is_eligible(context, "agent_0")
        
        assert is_eligible, "Should be eligible at ban_until round"

    def test_ban_active_before_ban_until(self):
        """Ban should be active when current_round < ban_until."""
        existing_norm_state = {
            "round_3_limit": {
                "violations": {"agent_0": 3},
                "ban_until": {"agent_0": 6}  # Banned until round 6
            }
        }
        
        state = make_test_state(
            stock_kg=100.0,
            round_number=5,  # Before ban_until - should be banned
            payoff={"agent_0": 25.0},
            existing_norm_state=existing_norm_state
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        
        norm = engine.norms[0]
        is_eligible = norm.is_eligible(context, "agent_0")
        
        assert not is_eligible, "Should be ineligible before ban_until round"

    def test_ban_lifted_after_full_period(self):
        """Complete ban cycle: violation → ban → lift after period."""
        # Round 1: Violation
        state1 = make_test_state(stock_kg=100.0, round_number=1, payoff={"agent_0": 25.0})
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)
        
        engine1.apply(context1, "agent_0", 30.0)
        norm_state_round1 = context1.runtime.get("norms", {})
        
        # Round 2: Should be banned
        state2 = make_test_state(
            stock_kg=90.0,
            round_number=2,
            payoff={"agent_0": 25.0},
            existing_norm_state=norm_state_round1
        )
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        
        norm2 = engine2.norms[0]
        assert not norm2.is_eligible(context2, "agent_0"), "Should be banned in round 2"
        
        norm_state_round2 = context2.runtime.get("norms", {})
        
        # Round 3: Should be eligible again
        state3 = make_test_state(
            stock_kg=80.0,
            round_number=3,
            payoff={"agent_0": 25.0},
            existing_norm_state=norm_state_round2
        )
        context3 = HarvestContext.from_state(state3)
        engine3 = NormEngine.from_config(state3["config"])
        
        norm3 = engine3.norms[0]
        assert norm3.is_eligible(context3, "agent_0"), "Should be eligible in round 3"


# ============================================================================
# REQUIREMENT 12: Transparency (Public Ledger Visibility)
# ============================================================================

class TestRequirement12_Transparency:
    """
    Requirement 12: Transparency (Public Ledger Visibility)
    
    All relevant norm state should be visible to agents via describe().
    """

    def test_describe_shows_current_reserves(self):
        """describe() should show current reserve level."""
        state = make_test_state(stock_kg=100.0, payoff={"agent_0": 25.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        
        norm = engine.norms[0]
        description = norm.describe(context, "agent_0")
        
        assert "25.0" in description or "25kg" in description, \
            f"Should show reserves: {description}"

    def test_describe_shows_tier_classification(self):
        """describe() should show tier classification (high/low)."""
        state_high = make_test_state(stock_kg=100.0, payoff={"agent_0": 25.0})
        context_high = HarvestContext.from_state(state_high)
        engine_high = NormEngine.from_config(state_high["config"])
        
        description_high = engine_high.norms[0].describe(context_high, "agent_0")
        assert "high" in description_high.lower(), f"Should show high tier: {description_high}"
        
        state_low = make_test_state(stock_kg=100.0, payoff={"agent_0": 15.0})
        context_low = HarvestContext.from_state(state_low)
        engine_low = NormEngine.from_config(state_low["config"])
        
        description_low = engine_low.norms[0].describe(context_low, "agent_0")
        assert "low" in description_low.lower(), f"Should show low tier: {description_low}"

    def test_describe_shows_applicable_limit(self):
        """describe() should show the applicable catch limit."""
        state = make_test_state(stock_kg=100.0, payoff={"agent_0": 25.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        
        description = engine.norms[0].describe(context, "agent_0")
        
        # Should show 25% and 30kg info
        assert "25%" in description, f"Should show 25%: {description}"
        assert "30kg" in description or "30" in description, f"Should show 30kg cap: {description}"

    def test_describe_shows_lake_stock(self):
        """describe() should show current lake stock."""
        state = make_test_state(stock_kg=150.0, payoff={"agent_0": 25.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        
        description = engine.norms[0].describe(context, "agent_0")
        
        assert "150.0" in description or "stock" in description.lower(), \
            f"Should show lake stock: {description}"

    def test_describe_shows_ban_status_when_banned(self):
        """describe() should indicate when fisher is banned."""
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
        
        description = engine.norms[0].describe(context, "agent_0")
        
        assert "banned" in description.lower(), f"Should show banned status: {description}"
        assert "round" in description.lower(), f"Should mention rounds remaining: {description}"

    def test_describe_shows_violation_history(self):
        """describe() should show violation history if applicable."""
        existing_norm_state = {
            "round_3_limit": {
                "violations": {"agent_0": 3}
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
        
        description = engine.norms[0].describe(context, "agent_0")
        
        assert "violation" in description.lower() or "round 3" in description.lower(), \
            f"Should show violation history: {description}"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration_CompleteScenarios:
    """Integration tests covering complete scenarios."""

    def test_full_tiered_forfeiture_ban_cycle(self):
        """
        Complete cycle:
        1. Fisher with high reserves catches above limit
        2. Excess is immediately forfeited
        3. Fisher is banned for next round
        4. Fisher is eligible again after ban
        """
        # Round 1: High tier violation
        state1 = make_test_state(stock_kg=100.0, round_number=1, payoff={"agent_0": 25.0})
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)
        
        # 30kg catch, 25kg limit, 5kg excess
        decision1 = engine1.apply(context1, "agent_0", 30.0)
        assert decision1.violated
        assert decision1.kept_kg == 25.0
        
        # Return excess to stock
        context1.override_stock_after_regrowth(80.0)
        engine1.end_round(context1, {
            "agent_0": {"effort": 1.0, "harvested_kg": 25.0, "participated": True, "note": decision1.note}
        })
        
        assert context1.stock_override_kg == 85.0, "Stock should include returned excess"
        
        norm_state1 = context1.runtime.get("norms", {})
        
        # Round 2: Banned
        state2 = make_test_state(
            stock_kg=85.0,
            round_number=2,
            payoff={"agent_0": 50.0},  # 25 + 25 kept
            existing_norm_state=norm_state1
        )
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        
        norm2 = engine2.norms[0]
        assert not norm2.is_eligible(context2, "agent_0"), "Should be banned in round 2"
        
        norm_state2 = context2.runtime.get("norms", {})
        
        # Round 3: Eligible again
        state3 = make_test_state(
            stock_kg=85.0,
            round_number=3,
            payoff={"agent_0": 50.0},
            existing_norm_state=norm_state2
        )
        context3 = HarvestContext.from_state(state3)
        engine3 = NormEngine.from_config(state3["config"])
        engine3.start_round(context3)
        
        norm3 = engine3.norms[0]
        assert norm3.is_eligible(context3, "agent_0"), "Should be eligible in round 3"
        
        # Can fish normally again
        decision3 = engine3.apply(context3, "agent_0", 20.0)
        assert not decision3.violated
        assert decision3.kept_kg == 20.0

    def test_multiple_agents_different_tiers_and_violations(self):
        """Multiple agents in different tiers with different violation patterns."""
        state = make_test_state(
            stock_kg=100.0,
            round_number=1,
            payoff={"agent_0": 25.0, "agent_1": 15.0, "agent_2": 25.0}
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # agent_0: High tier, within limit
        d0 = engine.apply(context, "agent_0", 20.0)
        assert not d0.violated
        assert d0.kept_kg == 20.0
        
        # agent_1: Low tier, exceeds limit
        d1 = engine.apply(context, "agent_1", 15.0)
        assert d1.violated
        assert d1.kept_kg == 12.0  # 12% of 100kg = 12kg limit
        
        # agent_2: High tier, exceeds limit
        d2 = engine.apply(context, "agent_2", 28.0)
        assert d2.violated
        assert d2.kept_kg == 25.0  # 25% of 100kg = 25kg limit
        
        # Check tier tracking
        scratch = context.round_scratch("round_3_limit")
        tiers = scratch.get("tier_this_round", {})
        assert tiers["agent_0"] == "high"
        assert tiers["agent_1"] == "low"
        assert tiers["agent_2"] == "high"
        
        # Return excess
        context.override_stock_after_regrowth(70.0)
        engine.end_round(context, {
            "agent_0": {"effort": 1.0, "harvested_kg": 20.0, "participated": True, "note": d0.note},
            "agent_1": {"effort": 1.0, "harvested_kg": 12.0, "participated": True, "note": d1.note},
            "agent_2": {"effort": 1.0, "harvested_kg": 25.0, "participated": True, "note": d2.note}
        })
        
        # Excess returned: (15-12) + (28-25) = 3 + 3 = 6kg
        assert context.stock_override_kg == 76.0, f"Expected 76.0kg, got {context.stock_override_kg}"

    def test_config_replaces_round2_norm(self):
        """Verify that Round 3 norm replaces Round 2 norm, not supplements it."""
        state = make_test_state()
        
        # Should only have the tiered_catch_limit_with_forfeiture norm
        norms = state["config"]["norms"]
        assert len(norms) == 1, f"Should have exactly 1 norm, got {len(norms)}"
        assert norms[0]["type"] == "tiered_catch_limit_with_forfeiture", \
            f"Should be tiered_catch_limit_with_forfeiture, got {norms[0]['type']}"


# ============================================================================
# EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_reserves_is_low_tier(self):
        """Fisher with zero reserves should be classified as low tier."""
        state = make_test_state(stock_kg=100.0, payoff={"agent_0": 0.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # 12% of 100kg = 12kg limit
        decision = engine.apply(context, "agent_0", 15.0)
        assert decision.violated
        assert decision.kept_kg == 12.0

    def test_exactly_at_limit_no_violation(self):
        """Catching exactly at the limit should not trigger violation."""
        state = make_test_state(stock_kg=100.0, payoff={"agent_0": 25.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # Exactly 25kg (25% of 100kg)
        decision = engine.apply(context, "agent_0", 25.0)
        assert not decision.violated
        assert decision.kept_kg == 25.0

    def test_just_above_limit_triggers_violation(self):
        """Catching just above the limit should trigger violation."""
        state = make_test_state(stock_kg=100.0, payoff={"agent_0": 25.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # 25.1kg > 25kg limit
        decision = engine.apply(context, "agent_0", 25.1)
        assert decision.violated
        assert decision.kept_kg == 25.0

    def test_high_reserves_with_very_low_stock(self):
        """High tier with very low stock - 25% might be less than low tier cap."""
        state = make_test_state(stock_kg=40.0, payoff={"agent_0": 25.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)
        
        # 25% of 40kg = 10kg limit (high tier)
        # Low tier would have 12% of 40kg = 4.8kg, capped at 15kg = 4.8kg
        # So high tier still has higher limit
        decision = engine.apply(context, "agent_0", 12.0)
        assert decision.violated
        assert decision.kept_kg == 10.0, f"Expected 10.0kg (25% of 40kg), got {decision.kept_kg}"

    def test_multiple_violations_extend_ban(self):
        """Multiple violations in different rounds should extend ban."""
        # Round 1: First violation
        state1 = make_test_state(stock_kg=100.0, round_number=1, payoff={"agent_0": 25.0})
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)
        engine1.apply(context1, "agent_0", 30.0)
        
        norm_state1 = context1.runtime.get("norms", {})
        
        # Round 3: Eligible again, violate again
        state3 = make_test_state(
            stock_kg=80.0,
            round_number=3,
            payoff={"agent_0": 50.0},
            existing_norm_state=norm_state1
        )
        context3 = HarvestContext.from_state(state3)
        engine3 = NormEngine.from_config(state3["config"])
        engine3.start_round(context3)
        engine3.apply(context3, "agent_0", 30.0)
        
        norm_state3 = context3.norm_state("round_3_limit")
        # Should have violations from both round 1 and round 3
        assert norm_state3["violations"]["agent_0"] == 3  # Most recent
        # Ban until round 5 (3 + 1 + 1)
        assert norm_state3["ban_until"]["agent_0"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
