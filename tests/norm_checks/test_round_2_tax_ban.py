"""
Independent tests for Round 2 norm implementation: catch_limit_with_tax_and_ban

Requirements to verify:
1. Catch limit enforcement (15% or 20kg) - violation detection only, no forfeiture
2. Tax on next catch (5kg) - after prior violation
3. Ban after violation - one trip ban
4. Community fund tracking - accumulates taxes
5. Minimum reserve requirement (1kg) - eligibility check
"""

import pytest
from engine.norms.context import HarvestContext
from engine.norms.engine import NormEngine


def make_test_state(stock_kg=100.0, round_number=1, payoff=None, existing_norm_state=None):
    """Create a minimal state for testing Round 2 norm."""
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
                    "type": "catch_limit_with_tax_and_ban",
                    "id": "round_2_limit",
                    "percent_limit": 0.15,
                    "kg_limit": 20.0,
                    "tax_kg": 5.0,
                    "min_reserve_kg": 1.0
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
# Requirement 1: Catch Limit Enforcement (15% or 20kg) - No Forfeiture
# ============================================================================

class TestCatchLimitEnforcement:
    """Test that catch limits are properly enforced WITHOUT forfeiture."""

    def test_catch_at_exactly_15_percent_allowed(self):
        """Catch at exactly 15% of stock should be allowed."""
        state = make_test_state(stock_kg=100.0)  # 15% = 15kg limit
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 15kg catch - exactly at 15% limit
        decision = engine.apply(context, "agent_0", 15.0)

        assert decision.kept_kg == 15.0
        assert not decision.violated

    def test_catch_at_exactly_20kg_allowed_when_stock_high(self):
        """Catch at exactly 20kg should be allowed when stock is high."""
        state = make_test_state(stock_kg=200.0)  # 15% = 30kg, so 20kg cap applies
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 20kg catch - exactly at 20kg cap
        decision = engine.apply(context, "agent_0", 20.0)

        assert decision.kept_kg == 20.0
        assert not decision.violated

    def test_catch_above_both_limits_triggers_violation_no_forfeiture(self):
        """Catch above both limits triggers violation but NO forfeiture - KEY DIFFERENCE FROM ROUND 1."""
        state = make_test_state(stock_kg=100.0)  # 15% = 15kg limit
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 25kg catch - exceeds both 15% (15kg) and 20kg
        decision = engine.apply(context, "agent_0", 25.0)

        assert decision.violated
        assert decision.sanction == "catch_limit_exceeded"
        assert decision.kept_kg == 25.0, f"Round 2: Full catch should be kept, but got {decision.kept_kg}kg"
        # KEY REQUIREMENT: No forfeiture - fisher keeps full 25kg

    def test_20kg_cap_applies_when_stock_high(self):
        """When 15% of stock > 20kg, the 20kg cap should apply."""
        state = make_test_state(stock_kg=200.0)  # 15% = 30kg, so 20kg cap
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 25kg exceeds 20kg cap
        decision = engine.apply(context, "agent_0", 25.0)

        assert decision.violated
        assert decision.kept_kg == 25.0  # No forfeiture - full catch kept

    def test_15_percent_applies_when_stock_low(self):
        """When 15% of stock < 20kg, the 15% limit should apply."""
        state = make_test_state(stock_kg=50.0)  # 15% = 7.5kg, so 7.5kg limit
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 10kg exceeds 7.5kg limit
        decision = engine.apply(context, "agent_0", 10.0)

        assert decision.violated
        assert decision.kept_kg == 10.0  # No forfeiture - full catch kept

    def test_catch_below_both_limits_allowed(self):
        """Catch below both limits should be allowed with no violation."""
        state = make_test_state(stock_kg=100.0)  # 15% = 15kg limit
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 10kg - below both limits
        decision = engine.apply(context, "agent_0", 10.0)

        assert not decision.violated
        assert decision.kept_kg == 10.0


# ============================================================================
# Requirement 2: Tax on Next Catch (5kg)
# ============================================================================

class TestTaxOnNextCatch:
    """Test that 5kg tax is deducted from the NEXT catch after a violation."""

    def test_tax_deducted_after_prior_violation(self):
        """After a violation in round 1, round 2 catch should have 5kg tax deducted."""
        # Round 1: Violation
        state1 = make_test_state(stock_kg=100.0, round_number=1)
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)

        decision1 = engine1.apply(context1, "agent_0", 25.0)
        assert decision1.violated  # Violation recorded

        # Get the norm state from round 1
        norm_state_round1 = context1.runtime.get("norms", {})

        # Round 2: Tax should be deducted
        state2 = make_test_state(
            stock_kg=90.0,
            round_number=2,
            existing_norm_state=norm_state_round1
        )
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        engine2.start_round(context2)

        # 15kg catch - should have 5kg tax deducted = 10kg kept
        decision2 = engine2.apply(context2, "agent_0", 15.0)

        assert decision2.kept_kg == 10.0, f"Expected 10kg (15-5 tax), got {decision2.kept_kg}kg"

    def test_tax_cannot_exceed_catch_amount(self):
        """Tax cannot be more than the actual catch."""
        # Round 1: Violation
        state1 = make_test_state(stock_kg=100.0, round_number=1)
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)

        engine1.apply(context1, "agent_0", 25.0)

        norm_state_round1 = context1.runtime.get("norms", {})

        # Round 2: Small catch
        state2 = make_test_state(
            stock_kg=90.0,
            round_number=2,
            existing_norm_state=norm_state_round1
        )
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        engine2.start_round(context2)

        # 3kg catch - tax is min(5kg, 3kg) = 3kg
        decision2 = engine2.apply(context2, "agent_0", 3.0)

        assert decision2.kept_kg == 0.0, f"Expected 0kg (3-3 tax), got {decision2.kept_kg}kg"

    def test_tax_payment_recorded_in_norm_state(self):
        """Tax payment should be tracked per agent."""
        # Round 1: Violation
        state1 = make_test_state(stock_kg=100.0, round_number=1)
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)

        engine1.apply(context1, "agent_0", 25.0)

        norm_state_round1 = context1.runtime.get("norms", {})

        # Round 2: Pay tax
        state2 = make_test_state(
            stock_kg=90.0,
            round_number=2,
            existing_norm_state=norm_state_round1
        )
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        engine2.start_round(context2)

        engine2.apply(context2, "agent_0", 15.0)

        norm_state = context2.norm_state("round_2_limit")
        assert norm_state["tax_paid"]["agent_0"] == 5.0

    def test_no_tax_without_prior_violation(self):
        """Agents without prior violations should pay no tax."""
        state = make_test_state(stock_kg=100.0, round_number=1)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # No prior violation
        decision = engine.apply(context, "agent_0", 10.0)

        assert decision.kept_kg == 10.0  # No tax

    def test_violation_cleared_after_tax_paid(self):
        """Violation should be cleared from state after tax is paid."""
        # Round 1: Violation
        state1 = make_test_state(stock_kg=100.0, round_number=1)
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)

        engine1.apply(context1, "agent_0", 25.0)

        norm_state_round1 = context1.runtime.get("norms", {})

        # Round 2: Pay tax
        state2 = make_test_state(
            stock_kg=90.0,
            round_number=2,
            existing_norm_state=norm_state_round1
        )
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        engine2.start_round(context2)

        engine2.apply(context2, "agent_0", 15.0)

        norm_state = context2.norm_state("round_2_limit")
        assert "agent_0" not in norm_state.get("violations", {}), "Violation should be cleared after tax paid"

    def test_tax_note_included_in_decision(self):
        """Decision note should mention the tax deduction."""
        # Round 1: Violation
        state1 = make_test_state(stock_kg=100.0, round_number=1)
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)

        engine1.apply(context1, "agent_0", 25.0)

        norm_state_round1 = context1.runtime.get("norms", {})

        # Round 2: Tax deduction
        state2 = make_test_state(
            stock_kg=90.0,
            round_number=2,
            existing_norm_state=norm_state_round1
        )
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        engine2.start_round(context2)

        decision2 = engine2.apply(context2, "agent_0", 15.0)

        assert "tax" in decision2.note.lower(), f"Note should mention tax: {decision2.note}"


# ============================================================================
# Requirement 3: Loss of Permission for Following Trip (Ban)
# ============================================================================

class TestBanAfterViolation:
    """Test that agents are banned for one trip after a violation."""

    def test_ban_recorded_after_violation(self):
        """Ban should be recorded in norm state after violation."""
        state = make_test_state(stock_kg=100.0, round_number=1)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        engine.apply(context, "agent_0", 25.0)

        norm_state = context.norm_state("round_2_limit")
        assert "agent_0" in norm_state.get("banned", {})
        # ban_until = current_round + 2 = 3 (banned for round 2, eligible at round 3)
        assert norm_state["banned"]["agent_0"] == 3

    def test_ineligible_during_ban_round(self):
        """Agent should be ineligible during the banned round."""
        # Round 1: Violation
        state1 = make_test_state(stock_kg=100.0, round_number=1)
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)

        engine1.apply(context1, "agent_0", 25.0)

        norm_state_round1 = context1.runtime.get("norms", {})

        # Round 2: Should be banned
        state2 = make_test_state(
            stock_kg=90.0,
            round_number=2,
            existing_norm_state=norm_state_round1
        )
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        engine2.start_round(context2)

        is_eligible = engine2.is_eligible(context2, "agent_0")
        assert not is_eligible, "Agent should be ineligible during ban round"

    def test_eligible_after_ban_expires(self):
        """Agent should be eligible again after ban expires."""
        # Round 1: Violation
        state1 = make_test_state(stock_kg=100.0, round_number=1, payoff={"agent_0": 10.0})
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)

        engine1.apply(context1, "agent_0", 25.0)

        norm_state_round1 = context1.runtime.get("norms", {})

        # Round 3: Ban should have expired (ban_until was 3)
        state3 = make_test_state(
            stock_kg=80.0,
            round_number=3,
            payoff={"agent_0": 10.0},
            existing_norm_state=norm_state_round1
        )
        context3 = HarvestContext.from_state(state3)
        engine3 = NormEngine.from_config(state3["config"])
        engine3.start_round(context3)

        is_eligible = engine3.is_eligible(context3, "agent_0")
        assert is_eligible, "Agent should be eligible after ban expires"

    def test_only_violating_agent_banned(self):
        """Only the agent who violated should be banned, not others."""
        state = make_test_state(stock_kg=100.0, round_number=1, payoff={"agent_0": 10.0, "agent_1": 10.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Agent 0 violates, agent 1 doesn't
        engine.apply(context, "agent_0", 25.0)
        engine.apply(context, "agent_1", 10.0)

        norm_state_round1 = context.runtime.get("norms", {})

        # Round 2
        state2 = make_test_state(
            stock_kg=90.0,
            round_number=2,
            payoff={"agent_0": 35.0, "agent_1": 20.0},
            existing_norm_state=norm_state_round1
        )
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        engine2.start_round(context2)

        assert not engine2.is_eligible(context2, "agent_0"), "Violating agent should be banned"
        assert engine2.is_eligible(context2, "agent_1"), "Non-violating agent should be eligible"

    def test_ban_description_shows_ban_status(self):
        """Description should indicate banned status."""
        # Round 1: Violation
        state1 = make_test_state(stock_kg=100.0, round_number=1, payoff={"agent_0": 10.0})
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)

        engine1.apply(context1, "agent_0", 25.0)

        norm_state_round1 = context1.runtime.get("norms", {})

        # Round 2: Description should show ban
        state2 = make_test_state(
            stock_kg=90.0,
            round_number=2,
            payoff={"agent_0": 35.0},
            existing_norm_state=norm_state_round1
        )
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        engine2.start_round(context2)

        description = engine2.describe_constraints(context2, "agent_0")
        assert "banned" in description.lower(), f"Description should show ban: {description}"


# ============================================================================
# Requirement 4: Community Fund Tracking
# ============================================================================

class TestCommunityFund:
    """Test that community fund tracks accumulated taxes."""

    def test_community_fund_increases_by_tax_amount(self):
        """Community fund should increase by tax amount when tax is paid."""
        # Round 1: Violation
        state1 = make_test_state(stock_kg=100.0, round_number=1)
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)

        engine1.apply(context1, "agent_0", 25.0)

        norm_state_round1 = context1.runtime.get("norms", {})

        # Round 2: Pay tax
        state2 = make_test_state(
            stock_kg=90.0,
            round_number=2,
            existing_norm_state=norm_state_round1
        )
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        engine2.start_round(context2)

        engine2.apply(context2, "agent_0", 15.0)

        norm_state = context2.norm_state("round_2_limit")
        assert norm_state["community_fund"] == 5.0, f"Community fund should be 5.0, got {norm_state.get('community_fund', 0)}"

    def test_community_fund_accumulates_multiple_taxes(self):
        """Community fund should accumulate taxes from multiple agents."""
        # Round 1: Two violations
        state1 = make_test_state(stock_kg=200.0, round_number=1)
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)

        engine1.apply(context1, "agent_0", 25.0)
        engine1.apply(context1, "agent_1", 25.0)

        norm_state_round1 = context1.runtime.get("norms", {})

        # Round 2: Both pay tax
        state2 = make_test_state(
            stock_kg=180.0,
            round_number=2,
            existing_norm_state=norm_state_round1
        )
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        engine2.start_round(context2)

        engine2.apply(context2, "agent_0", 15.0)
        engine2.apply(context2, "agent_1", 15.0)

        norm_state = context2.norm_state("round_2_limit")
        assert norm_state["community_fund"] == 10.0, f"Community fund should be 10.0 (5+5), got {norm_state.get('community_fund', 0)}"

    def test_community_fund_persists_across_rounds(self):
        """Community fund should persist and accumulate across rounds."""
        # Round 1: Violation
        state1 = make_test_state(stock_kg=100.0, round_number=1)
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)

        engine1.apply(context1, "agent_0", 25.0)

        norm_state_round1 = context1.runtime.get("norms", {})

        # Round 2: Pay tax + new violation
        state2 = make_test_state(
            stock_kg=90.0,
            round_number=2,
            existing_norm_state=norm_state_round1
        )
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        engine2.start_round(context2)

        # Pay tax from round 1, then violate again
        engine2.apply(context2, "agent_0", 25.0)

        norm_state_round2 = context2.runtime.get("norms", {})

        # Round 3: Pay tax again
        state3 = make_test_state(
            stock_kg=75.0,
            round_number=3,
            existing_norm_state=norm_state_round2
        )
        context3 = HarvestContext.from_state(state3)
        engine3 = NormEngine.from_config(state3["config"])
        engine3.start_round(context3)

        engine3.apply(context3, "agent_0", 15.0)

        norm_state = context3.norm_state("round_2_limit")
        assert norm_state["community_fund"] == 10.0, f"Community fund should be 10.0 (5+5), got {norm_state.get('community_fund', 0)}"

    def test_description_shows_community_fund(self):
        """Description should show current community fund balance."""
        # Round 1: Violation, pay tax, and another violation
        state1 = make_test_state(stock_kg=100.0, round_number=1, payoff={"agent_0": 10.0})
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)

        engine1.apply(context1, "agent_0", 25.0)

        norm_state_round1 = context1.runtime.get("norms", {})

        # Round 2: Pay tax and get new violation (so we can check description in round 3 when not banned)
        state2 = make_test_state(
            stock_kg=90.0,
            round_number=2,
            payoff={"agent_0": 35.0},
            existing_norm_state=norm_state_round1
        )
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        engine2.start_round(context2)

        # Pay tax and get another violation
        engine2.apply(context2, "agent_0", 25.0)

        norm_state_round2 = context2.runtime.get("norms", {})

        # Round 4: Eligible again (ban expired), check description shows community fund
        state4 = make_test_state(
            stock_kg=70.0,
            round_number=4,
            payoff={"agent_0": 55.0},
            existing_norm_state=norm_state_round2
        )
        context4 = HarvestContext.from_state(state4)
        engine4 = NormEngine.from_config(state4["config"])
        engine4.start_round(context4)

        description = engine4.describe_constraints(context4, "agent_0")
        assert "community fund" in description.lower(), f"Description should show community fund: {description}"


# ============================================================================
# Requirement 5: Minimum Reserve Requirement (1kg)
# ============================================================================

class TestMinimumReserve:
    """Test that fishers need at least 1kg reserve to fish."""

    def test_ineligible_below_minimum_reserve(self):
        """Agent with < 1kg reserve should be ineligible."""
        state = make_test_state(
            stock_kg=100.0,
            round_number=1,
            payoff={"agent_0": 0.5}  # Below 1kg minimum
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        is_eligible = engine.is_eligible(context, "agent_0")
        assert not is_eligible, "Agent with 0.5kg reserve should be ineligible"

    def test_eligible_at_exact_minimum_reserve(self):
        """Agent with exactly 1kg reserve should be eligible."""
        state = make_test_state(
            stock_kg=100.0,
            round_number=1,
            payoff={"agent_0": 1.0}  # Exactly at 1kg minimum
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        is_eligible = engine.is_eligible(context, "agent_0")
        assert is_eligible, "Agent with 1.0kg reserve should be eligible"

    def test_eligible_above_minimum_reserve(self):
        """Agent with > 1kg reserve should be eligible."""
        state = make_test_state(
            stock_kg=100.0,
            round_number=1,
            payoff={"agent_0": 5.0}  # Above 1kg minimum
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        is_eligible = engine.is_eligible(context, "agent_0")
        assert is_eligible, "Agent with 5.0kg reserve should be eligible"

    def test_ineligible_with_zero_reserve(self):
        """Agent with 0 reserve should be ineligible."""
        state = make_test_state(
            stock_kg=100.0,
            round_number=1,
            payoff={"agent_0": 0.0}
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        is_eligible = engine.is_eligible(context, "agent_0")
        assert not is_eligible, "Agent with 0kg reserve should be ineligible"

    def test_description_shows_low_reserve(self):
        """Description should indicate low reserve status."""
        state = make_test_state(
            stock_kg=100.0,
            round_number=1,
            payoff={"agent_0": 0.5}
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        description = engine.describe_constraints(context, "agent_0")
        assert "reserve" in description.lower(), f"Description should mention reserve requirement: {description}"


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests combining multiple scenarios."""

    def test_full_violation_tax_ban_cycle(self):
        """Complete cycle: violation → tax + ban next round → resume after."""
        # Round 1: Violation
        state1 = make_test_state(
            stock_kg=200.0,
            round_number=1,
            payoff={"agent_0": 10.0}
        )
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)

        decision1 = engine1.apply(context1, "agent_0", 25.0)
        assert decision1.violated
        assert decision1.kept_kg == 25.0  # No forfeiture

        norm_state_round1 = context1.runtime.get("norms", {})

        # Round 2: Banned (can't fish)
        state2 = make_test_state(
            stock_kg=175.0,
            round_number=2,
            payoff={"agent_0": 35.0},  # 10 + 25 kept
            existing_norm_state=norm_state_round1
        )
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        engine2.start_round(context2)

        assert not engine2.is_eligible(context2, "agent_0"), "Should be banned in round 2"

        norm_state_round2 = context2.runtime.get("norms", {})

        # Round 3: Eligible again, but pays tax
        state3 = make_test_state(
            stock_kg=175.0,
            round_number=3,
            payoff={"agent_0": 35.0},
            existing_norm_state=norm_state_round2
        )
        context3 = HarvestContext.from_state(state3)
        engine3 = NormEngine.from_config(state3["config"])
        engine3.start_round(context3)

        assert engine3.is_eligible(context3, "agent_0"), "Should be eligible in round 3"

        # Pay tax from round 1 violation
        decision3 = engine3.apply(context3, "agent_0", 15.0)
        assert decision3.kept_kg == 10.0  # 15 - 5 tax

        # Check community fund
        norm_state = context3.norm_state("round_2_limit")
        assert norm_state["community_fund"] == 5.0

    def test_description_shows_all_constraints(self):
        """Description should show all relevant constraints."""
        state = make_test_state(
            stock_kg=100.0,
            round_number=1,
            payoff={"agent_0": 5.0}
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        description = engine.describe_constraints(context, "agent_0")

        # Should show limit info
        assert "15%" in description or "15" in description, f"Should show 15% limit: {description}"
        assert "20" in description, f"Should show 20kg cap: {description}"
        # Should show tax info
        assert "5kg" in description or "5 kg" in description, f"Should show 5kg tax: {description}"
        # Should show community fund
        assert "community fund" in description.lower(), f"Should show community fund: {description}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
