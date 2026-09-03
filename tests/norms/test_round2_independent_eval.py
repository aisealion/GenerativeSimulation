"""
Independent evaluation tests for Round 2 norm implementation.

These tests verify the requirements from state/norm_specs/round_2.md:
- R1: Per-trip catch limit (percentage-based): harvested_kg <= 0.125 * stock_before
- R2: Excess release: If raw_kg > 0.125 * stock, then kept_kg <= 0.125 * stock
- R3: Penalty for overage: penalty = 0.5 * (raw_kg - limit), final_kept = limit - penalty
- R4: Three-strike ban: After 3 violations with sanction "over_cap", is_eligible returns False for 2 trips
"""

import pytest
from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.catch_limit import CatchLimitNorm
from norms.overage_penalty import OveragePenaltyNorm
from norms.strike_ban import StrikeBanNorm


def _context(stock=1000.0):
    """Create a HarvestContext with specified stock level."""
    return HarvestContext.from_state({
        "config": {},
        "fluents": [],
        "runtime": {"stock_kg": stock},
        "agents": {},
        "round_number": 1,
    })


class TestR1_PerTripCatchLimit:
    """R1: Each fisher's kept catch shall not exceed 12.5% of the current lake biomass."""

    def test_12_5_percent_limit_calculated_correctly(self):
        """With stock=1000kg, limit should be exactly 125kg."""
        context = _context(stock=1000.0)
        norm = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        
        # Agent tries to catch 200kg, should be limited to 125kg (12.5% of 1000)
        decision = norm.evaluate(context, "agent_0", raw_kg=200.0, proposed_kg=200.0)
        
        assert decision.kept_kg == 125.0, f"Expected 125.0kg (12.5% of 1000), got {decision.kept_kg}kg"
        assert decision.violated is True
        assert decision.sanction == "over_cap"

    def test_12_5_percent_with_different_stock_levels(self):
        """Limit should scale with stock level."""
        norm = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        
        # Stock = 800kg, limit = 100kg
        context1 = _context(stock=800.0)
        decision1 = norm.evaluate(context1, "agent_0", raw_kg=150.0, proposed_kg=150.0)
        assert decision1.kept_kg == 100.0, f"Expected 100.0kg (12.5% of 800), got {decision1.kept_kg}kg"
        
        # Stock = 200kg, limit = 25kg
        context2 = _context(stock=200.0)
        decision2 = norm.evaluate(context2, "agent_0", raw_kg=50.0, proposed_kg=50.0)
        assert decision2.kept_kg == 25.0, f"Expected 25.0kg (12.5% of 200), got {decision2.kept_kg}kg"

    def test_under_limit_unchanged(self):
        """Catch below 12.5% should not be affected."""
        context = _context(stock=1000.0)
        norm = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        
        # Agent catches 100kg (below 125kg limit)
        decision = norm.evaluate(context, "agent_0", raw_kg=100.0, proposed_kg=100.0)
        
        assert decision.kept_kg == 100.0
        assert decision.violated is False

    def test_exactly_at_limit(self):
        """Catch exactly at 12.5% should be allowed."""
        context = _context(stock=1000.0)
        norm = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        
        decision = norm.evaluate(context, "agent_0", raw_kg=125.0, proposed_kg=125.0)
        
        assert decision.kept_kg == 125.0
        assert decision.violated is False


class TestR2_ExcessRelease:
    """R2: Any catch amount above the 12.5% limit must be released (not kept)."""

    def test_excess_above_12_5_percent_is_not_kept(self):
        """When raw catch exceeds 12.5%, only 12.5% should be kept."""
        context = _context(stock=1000.0)
        norm = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        
        # Agent catches 200kg, but limit is 125kg
        raw_catch = 200.0
        limit = 125.0  # 12.5% of 1000
        
        decision = norm.evaluate(context, "agent_0", raw_kg=raw_catch, proposed_kg=raw_catch)
        
        assert decision.kept_kg <= limit, f"Kept {decision.kept_kg}kg but limit is {limit}kg"
        assert decision.kept_kg == limit, f"Expected exactly {limit}kg to be kept"

    def test_excess_amount_calculated_correctly(self):
        """Verify excess amount is the difference between raw and limit."""
        context = _context(stock=1000.0)
        norm = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        
        raw_catch = 200.0
        limit = 125.0
        expected_excess = raw_catch - limit  # 75kg
        
        decision = norm.evaluate(context, "agent_0", raw_kg=raw_catch, proposed_kg=raw_catch)
        
        excess_not_kept = raw_catch - decision.kept_kg
        assert excess_not_kept == expected_excess, f"Excess should be {expected_excess}kg, but {excess_not_kept}kg was not kept"


class TestR3_PenaltyForOverage:
    """R3: penalty = 0.5 * (raw_kg - limit), penalty added to community fund."""

    def test_penalty_is_50_percent_of_overage(self):
        """Penalty should be exactly 50% of the overage amount."""
        context = _context(stock=1000.0)
        penalty_norm = OveragePenaltyNorm(key="overage_penalty", params={
            "penalty_pct": 0.5,
            "target_fund": "community_fund"
        })
        
        # Agent tried to catch 200kg, was limited to 125kg
        raw_kg = 200.0
        proposed_kg = 125.0  # After catch_limit
        overage = raw_kg - proposed_kg  # 75kg
        expected_penalty = overage * 0.5  # 37.5kg
        expected_final_kept = proposed_kg - expected_penalty  # 125 - 37.5 = 87.5kg
        
        decision = penalty_norm.evaluate(context, "agent_0", raw_kg=raw_kg, proposed_kg=proposed_kg)
        
        assert decision.kept_kg == expected_final_kept, f"Expected {expected_final_kept}kg, got {decision.kept_kg}kg"

    def test_penalty_added_to_community_fund(self):
        """The penalty amount should be tracked in the community fund."""
        context = _context(stock=1000.0)
        penalty_norm = OveragePenaltyNorm(key="overage_penalty", params={
            "penalty_pct": 0.5,
            "target_fund": "community_fund"
        })
        
        raw_kg = 200.0
        proposed_kg = 125.0
        overage = raw_kg - proposed_kg  # 75kg
        expected_penalty = overage * 0.5  # 37.5kg
        
        penalty_norm.evaluate(context, "agent_0", raw_kg=raw_kg, proposed_kg=proposed_kg)
        
        fund = context.norm_state("overage_penalty").get("community_fund", 0.0)
        assert fund == expected_penalty, f"Community fund should have {expected_penalty}kg, has {fund}kg"

    def test_full_penalty_calculation_formula(self):
        """Verify the complete penalty formula: final_kept = 1.5*L - 0.5*X where L=limit, X=raw."""
        context = _context(stock=1000.0)
        penalty_norm = OveragePenaltyNorm(key="overage_penalty", params={
            "penalty_pct": 0.5,
            "target_fund": "community_fund"
        })
        
        raw_kg = 200.0
        limit = 125.0
        # Formula: final_kept = 1.5*L - 0.5*X = 1.5*125 - 0.5*200 = 187.5 - 100 = 87.5
        expected_final_kept = 1.5 * limit - 0.5 * raw_kg
        
        decision = penalty_norm.evaluate(context, "agent_0", raw_kg=raw_kg, proposed_kg=limit)
        
        assert decision.kept_kg == expected_final_kept, f"Expected {expected_final_kept}kg based on formula, got {decision.kept_kg}kg"

    def test_multiple_penalties_accumulate(self):
        """Multiple penalties from different agents should accumulate in the fund."""
        context = _context(stock=1000.0)
        penalty_norm = OveragePenaltyNorm(key="overage_penalty", params={
            "penalty_pct": 0.5,
            "target_fund": "community_fund"
        })
        
        # Agent 0: 200kg raw, 125kg limit -> 75kg overage, 37.5kg penalty
        penalty_norm.evaluate(context, "agent_0", raw_kg=200.0, proposed_kg=125.0)
        # Agent 1: 180kg raw, 125kg limit -> 55kg overage, 27.5kg penalty
        penalty_norm.evaluate(context, "agent_1", raw_kg=180.0, proposed_kg=125.0)
        
        fund = context.norm_state("overage_penalty").get("community_fund", 0.0)
        expected_total = 37.5 + 27.5  # 65kg
        assert fund == expected_total, f"Community fund should have {expected_total}kg, has {fund}kg"

    def test_no_penalty_when_no_overage(self):
        """When there's no overage, no penalty should be applied."""
        context = _context(stock=1000.0)
        penalty_norm = OveragePenaltyNorm(key="overage_penalty", params={
            "penalty_pct": 0.5,
            "target_fund": "community_fund"
        })
        
        decision = penalty_norm.evaluate(context, "agent_0", raw_kg=100.0, proposed_kg=100.0)
        
        assert decision.kept_kg == 100.0
        fund = context.norm_state("overage_penalty").get("community_fund", 0.0)
        assert fund == 0.0, f"No penalty should be added when no overage, but fund has {fund}kg"


class TestR4_ThreeStrikeBan:
    """R4: After 3 violations with sanction 'over_cap', is_eligible returns False for 2 trips."""

    def test_three_strikes_trigger_ban(self):
        """Exactly 3 strikes should trigger a ban."""
        context = _context(stock=1000.0)
        strike_norm = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap",
            "strikes": 3,
            "ban_trips": 2
        })
        
        decision = NormDecision(kept_kg=125.0, sanction="over_cap", violated=True)
        
        # First 2 strikes - should still be eligible
        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=125.0)
        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=125.0)
        assert strike_norm.is_eligible(context, "agent_0") is True, "Should be eligible after 2 strikes"
        
        # Third strike - should trigger ban
        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=125.0)
        ban_remaining = context.norm_state("strike_ban")["agent_0"]["ban_remaining"]
        assert ban_remaining == 2, f"Ban should be for 2 trips, got {ban_remaining}"

    def test_ban_blocks_eligibility_for_exactly_2_trips(self):
        """After ban is triggered, is_eligible should return False for exactly 2 trips."""
        context = _context(stock=1000.0)
        strike_norm = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap",
            "strikes": 3,
            "ban_trips": 2
        })
        
        # Manually set up banned state
        context.norm_state("strike_ban")["agent_0"] = {"strikes": 3, "ban_remaining": 2}
        
        # First call - should be ineligible, decrements to 1
        assert strike_norm.is_eligible(context, "agent_0") is False, "Should be banned (trip 1)"
        assert context.norm_state("strike_ban")["agent_0"]["ban_remaining"] == 1
        
        # Second call - should be ineligible, decrements to 0
        assert strike_norm.is_eligible(context, "agent_0") is False, "Should be banned (trip 2)"
        assert context.norm_state("strike_ban")["agent_0"]["ban_remaining"] == 0
        
        # Third call - should be eligible again
        assert strike_norm.is_eligible(context, "agent_0") is True, "Should be eligible after ban"

    def test_only_over_cap_sanction_counts(self):
        """Only violations with 'over_cap' sanction should count as strikes."""
        context = _context(stock=1000.0)
        strike_norm = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap",
            "strikes": 3,
            "ban_trips": 2
        })
        
        # Different sanction should not count
        other_decision = NormDecision(kept_kg=100.0, sanction="other_violation", violated=True)
        strike_norm.on_agent_settled(context, "agent_0", other_decision, harvested_kg=100.0)
        
        # No state should be created for non-matching sanction
        assert "agent_0" not in context.norm_state("strike_ban"), "Non-matching sanction should not create state"

    def test_strikes_reset_after_ban_completes(self):
        """After the ban period, strikes should be reset to 0."""
        context = _context(stock=1000.0)
        strike_norm = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap",
            "strikes": 3,
            "ban_trips": 2
        })
        
        # Set up state with 1 ban trip remaining
        context.norm_state("strike_ban")["agent_0"] = {"strikes": 3, "ban_remaining": 1}
        
        # Call is_eligible which decrements and resets
        strike_norm.is_eligible(context, "agent_0")
        
        state = context.norm_state("strike_ban")["agent_0"]
        assert state["strikes"] == 0, f"Strikes should be reset to 0, got {state['strikes']}"
        assert state["ban_remaining"] == 0, f"Ban should be complete, got {state['ban_remaining']}"


class TestNormIntegration:
    """Test that all three norms work together correctly."""

    def test_full_round2_workflow_single_violation(self):
        """Complete workflow: catch_limit caps, overage_penalty applies, strike_ban counts."""
        context = _context(stock=1000.0)
        
        # Setup norms as they would be in config
        catch_limit = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        overage_penalty = OveragePenaltyNorm(key="overage_penalty", params={
            "penalty_pct": 0.5,
            "target_fund": "community_fund"
        })
        strike_ban = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap",
            "strikes": 3,
            "ban_trips": 2
        })
        
        raw_kg = 200.0
        limit = 125.0  # 12.5% of 1000
        
        # Step 1: catch_limit caps the catch
        decision1 = catch_limit.evaluate(context, "agent_0", raw_kg=raw_kg, proposed_kg=raw_kg)
        assert decision1.kept_kg == limit
        assert decision1.sanction == "over_cap"
        
        # Step 2: overage_penalty applies 50% penalty on overage
        decision2 = overage_penalty.evaluate(context, "agent_0", raw_kg=raw_kg, proposed_kg=decision1.kept_kg)
        overage = raw_kg - limit  # 75kg
        expected_penalty = overage * 0.5  # 37.5kg
        expected_final = limit - expected_penalty  # 87.5kg
        assert decision2.kept_kg == expected_final
        
        # Step 3: strike_ban counts the violation
        strike_ban.on_agent_settled(context, "agent_0", decision1, harvested_kg=decision2.kept_kg)
        assert context.norm_state("strike_ban")["agent_0"]["strikes"] == 1
        
        # Verify penalty is in community fund
        fund = context.norm_state("overage_penalty").get("community_fund", 0.0)
        assert fund == expected_penalty

    def test_full_round2_workflow_three_violations_leads_to_ban(self):
        """Three violations should lead to a ban."""
        context = _context(stock=1000.0)
        
        catch_limit = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        overage_penalty = OveragePenaltyNorm(key="overage_penalty", params={
            "penalty_pct": 0.5,
            "target_fund": "community_fund"
        })
        strike_ban = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap",
            "strikes": 3,
            "ban_trips": 2
        })
        
        raw_kg = 200.0
        limit = 125.0
        
        # Three violations
        for i in range(3):
            decision1 = catch_limit.evaluate(context, "agent_0", raw_kg=raw_kg, proposed_kg=raw_kg)
            decision2 = overage_penalty.evaluate(context, "agent_0", raw_kg=raw_kg, proposed_kg=decision1.kept_kg)
            strike_ban.on_agent_settled(context, "agent_0", decision1, harvested_kg=decision2.kept_kg)
        
        # Should now have 3 strikes and ban should be active
        assert context.norm_state("strike_ban")["agent_0"]["strikes"] == 3
        assert context.norm_state("strike_ban")["agent_0"]["ban_remaining"] == 2
        
        # Agent should be ineligible
        assert strike_ban.is_eligible(context, "agent_0") is False


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_stock(self):
        """Test behavior when stock is zero."""
        context = _context(stock=0.0)
        norm = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        
        decision = norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
        
        # 12.5% of 0 is 0, so everything should be excess
        assert decision.kept_kg == 0.0
        assert decision.violated is True

    def test_very_small_stock(self):
        """Test with very small stock levels."""
        context = _context(stock=10.0)
        norm = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        
        # 12.5% of 10 = 1.25kg
        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)
        assert decision.kept_kg == 1.25

    def test_penalty_never_negative(self):
        """Final kept amount should never go below zero."""
        context = _context(stock=100.0)
        penalty_norm = OveragePenaltyNorm(key="overage_penalty", params={
            "penalty_pct": 1.0,  # 100% penalty
            "target_fund": "community_fund"
        })
        
        # Large overage with 100% penalty
        decision = penalty_norm.evaluate(context, "agent_0", raw_kg=100.0, proposed_kg=10.0)
        
        assert decision.kept_kg >= 0.0, f"Kept amount should never be negative, got {decision.kept_kg}"
        assert decision.kept_kg == 0.0

    def test_strikes_persist_across_separate_calls(self):
        """Strike counts should persist across separate norm instances (simulating rounds)."""
        # First round - 2 violations
        context1 = _context(stock=1000.0)
        strike_norm1 = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap",
            "strikes": 3,
            "ban_trips": 2
        })
        
        decision = NormDecision(kept_kg=125.0, sanction="over_cap", violated=True)
        strike_norm1.on_agent_settled(context1, "agent_0", decision, harvested_kg=125.0)
        strike_norm1.on_agent_settled(context1, "agent_0", decision, harvested_kg=125.0)
        
        # Simulate next round - new norm instance but same runtime state
        context2 = _context(stock=1000.0)
        context2.runtime["norms"] = context1.runtime["norms"]  # Persist state
        strike_norm2 = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap",
            "strikes": 3,
            "ban_trips": 2
        })
        
        # Third violation should trigger ban
        strike_norm2.on_agent_settled(context2, "agent_0", decision, harvested_kg=125.0)
        
        assert context2.norm_state("strike_ban")["agent_0"]["ban_remaining"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
