"""
Independent evaluation tests for Round 2 norm implementation.
Tests all requirements from state/norm_specs/round_2.md without relying on implementer's tests.
"""

import json
import pytest
from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.catch_limit import CatchLimitNorm
from norms.overage_penalty import OveragePenaltyNorm
from norms.strike_ban import StrikeBanNorm


def _context(stock_kg=100.0, round_num=1):
    """Helper to create a harvest context."""
    return HarvestContext.from_state({
        "config": {},
        "fluents": [],
        "runtime": {"stock_kg": stock_kg},
        "agents": {},
        "round_number": round_num,
    })


class TestR1_PerTripCatchLimit:
    """
    R1: Each fisher's kept catch shall not exceed 12.5% of the current lake biomass.
    Test: harvested_kg(agent, trip) <= 0.125 * stock_before
    """

    def test_exactly_12_5_percent_is_allowed(self):
        """Catch at exactly 12.5% should be fully kept."""
        norm = CatchLimitNorm(key="limit", params={"limit_pct_of_stock": 0.125})
        context = _context(stock_kg=100.0)

        # 12.5% of 100kg = 12.5kg
        decision = norm.evaluate(context, "agent_0", raw_kg=12.5, proposed_kg=12.5)

        assert decision.kept_kg == 12.5, f"Expected 12.5kg kept, got {decision.kept_kg}"
        assert decision.violated is False, "Should not be a violation at exact limit"

    def test_below_12_5_percent_is_allowed(self):
        """Catch below 12.5% should be fully kept."""
        norm = CatchLimitNorm(key="limit", params={"limit_pct_of_stock": 0.125})
        context = _context(stock_kg=100.0)

        decision = norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)

        assert decision.kept_kg == 10.0, f"Expected 10.0kg kept, got {decision.kept_kg}"
        assert decision.violated is False, "Should not be a violation below limit"

    def test_above_12_5_percent_is_capped(self):
        """Catch above 12.5% should be limited to 12.5%."""
        norm = CatchLimitNorm(key="limit", params={"limit_pct_of_stock": 0.125})
        context = _context(stock_kg=100.0)

        # Try to catch 20kg, should be limited to 12.5kg
        decision = norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=20.0)

        assert decision.kept_kg == 12.5, f"Expected 12.5kg kept, got {decision.kept_kg}"
        assert decision.violated is True, "Should be a violation when over limit"

    def test_limit_scales_with_biomass_at_200kg(self):
        """At 200kg stock, limit should be 25kg."""
        norm = CatchLimitNorm(key="limit", params={"limit_pct_of_stock": 0.125})
        context = _context(stock_kg=200.0)

        decision = norm.evaluate(context, "agent_0", raw_kg=100.0, proposed_kg=100.0)

        assert decision.kept_kg == 25.0, f"Expected 25.0kg (12.5% of 200), got {decision.kept_kg}"

    def test_limit_scales_with_biomass_at_80kg(self):
        """At 80kg stock, limit should be 10kg."""
        norm = CatchLimitNorm(key="limit", params={"limit_pct_of_stock": 0.125})
        context = _context(stock_kg=80.0)

        decision = norm.evaluate(context, "agent_0", raw_kg=100.0, proposed_kg=100.0)

        assert decision.kept_kg == 10.0, f"Expected 10.0kg (12.5% of 80), got {decision.kept_kg}"


class TestR2_ExcessRelease:
    """
    R2: Any catch amount above the 12.5% limit must be released (not kept).
    Test: If raw_kg > 0.125 * stock, then kept_kg <= 0.125 * stock
    """

    def test_excess_is_not_kept_when_over_limit(self):
        """When catching 20kg with 12.5kg limit, only 12.5kg is kept."""
        norm = CatchLimitNorm(key="limit", params={"limit_pct_of_stock": 0.125})
        context = _context(stock_kg=100.0)

        decision = norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=20.0)

        # 7.5kg should be "released" (not kept)
        assert decision.kept_kg <= 12.5, f"Kept {decision.kept_kg}kg but limit is 12.5kg"
        assert decision.kept_kg == 12.5, f"Expected exactly 12.5kg kept, got {decision.kept_kg}"

    def test_no_release_when_under_limit(self):
        """When catching 10kg with 12.5kg limit, all 10kg is kept."""
        norm = CatchLimitNorm(key="limit", params={"limit_pct_of_stock": 0.125})
        context = _context(stock_kg=100.0)

        decision = norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)

        assert decision.kept_kg == 10.0, f"Expected all 10kg kept, got {decision.kept_kg}"

    def test_sanction_is_set_on_over_cap(self):
        """Violation should have 'over_cap' sanction for downstream norms."""
        norm = CatchLimitNorm(key="limit", params={"limit_pct_of_stock": 0.125})
        context = _context(stock_kg=100.0)

        decision = norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=20.0)

        assert decision.sanction == "over_cap", f"Expected sanction 'over_cap', got {decision.sanction}"


class TestR3_PenaltyForOverage:
    """
    R3: Fishers who exceed the 12.5% limit must pay a penalty equal to 50% of the overage to the community.
    Test: If raw_kg > limit, then penalty = 0.5 * (raw_kg - limit) and final_kept = limit - penalty,
          with penalty added to community fund
    """

    def test_penalty_calculation_50_percent(self):
        """Penalty should be exactly 50% of overage."""
        penalty_norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})
        context = _context(stock_kg=100.0)

        # Agent caught 20kg, was limited to 12.5kg
        # Overage = 7.5kg
        # Penalty = 50% of 7.5kg = 3.75kg
        # Final kept = 12.5kg - 3.75kg = 8.75kg
        decision = penalty_norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=12.5)

        expected_penalty = 3.75
        expected_kept = 12.5 - expected_penalty  # 8.75

        assert decision.kept_kg == expected_kept, f"Expected {expected_kept}kg kept, got {decision.kept_kg}"

    def test_penalty_added_to_community_fund(self):
        """Penalty amount should be tracked in community_fund."""
        penalty_norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})
        context = _context(stock_kg=100.0)

        # 20kg raw, 12.5kg proposed -> 7.5kg overage, 3.75kg penalty
        penalty_norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=12.5)

        fund = context.norm_state("penalty").get("community_fund", 0.0)
        expected_fund = 3.75

        assert fund == expected_fund, f"Expected community_fund={expected_fund}, got {fund}"

    def test_penalty_accumulates_in_fund(self):
        """Multiple penalties should accumulate in community fund."""
        penalty_norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})
        context = _context(stock_kg=100.0)

        # Agent 0: 20kg raw, 12.5kg proposed -> 3.75kg penalty
        penalty_norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=12.5)
        # Agent 1: 30kg raw, 12.5kg proposed -> 17.5kg overage, 8.75kg penalty
        penalty_norm.evaluate(context, "agent_1", raw_kg=30.0, proposed_kg=12.5)

        fund = context.norm_state("penalty").get("community_fund", 0.0)
        expected_fund = 3.75 + 8.75  # 12.5

        assert fund == expected_fund, f"Expected community_fund={expected_fund}, got {fund}"

    def test_no_penalty_when_no_overage(self):
        """No penalty when proposed_kg equals raw_kg (no overage)."""
        penalty_norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})
        context = _context(stock_kg=100.0)

        decision = penalty_norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)

        assert decision.kept_kg == 10.0, f"Expected 10kg kept, got {decision.kept_kg}"

        fund = context.norm_state("penalty").get("community_fund", 0.0)
        assert fund == 0.0, f"Expected no fund contribution, got {fund}"


class TestR4_ThreeStrikeBan:
    """
    R4: A fisher who exceeds the limit three times receives a temporary fishing ban.
    Test: After 3 violations with sanction "over_cap", is_eligible(agent) returns False for 2 subsequent rounds
    """

    def test_single_violation_increments_strike_count(self):
        """One violation should result in 1 strike."""
        strike_norm = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2
        })
        context = _context(stock_kg=100.0)

        decision = NormDecision(kept_kg=10.0, sanction="over_cap", violated=True)
        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)

        strikes = context.norm_state("strike_ban")["agent_0"]["strikes"]
        assert strikes == 1, f"Expected 1 strike, got {strikes}"

    def test_two_violations_no_ban_yet(self):
        """Two violations should not trigger ban yet."""
        strike_norm = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2
        })
        context = _context(stock_kg=100.0)

        decision = NormDecision(kept_kg=10.0, sanction="over_cap", violated=True)
        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)

        ban_remaining = context.norm_state("strike_ban")["agent_0"]["ban_remaining"]
        assert ban_remaining == 0, f"Expected ban_remaining=0 after 2 strikes, got {ban_remaining}"

        is_eligible = strike_norm.is_eligible(context, "agent_0")
        assert is_eligible is True, "Agent should still be eligible after 2 strikes"

    def test_three_violations_triggers_ban(self):
        """Three violations should trigger a ban of 2 trips."""
        strike_norm = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2
        })
        context = _context(stock_kg=100.0)

        decision = NormDecision(kept_kg=10.0, sanction="over_cap", violated=True)
        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)

        ban_remaining = context.norm_state("strike_ban")["agent_0"]["ban_remaining"]
        assert ban_remaining == 2, f"Expected ban_remaining=2 after 3 strikes, got {ban_remaining}"

    def test_ban_blocks_eligibility_for_two_trips(self):
        """Banned agent should be ineligible for exactly 2 trips."""
        strike_norm = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2
        })
        context = _context(stock_kg=100.0)

        # Set up banned state directly
        context.norm_state("strike_ban")["agent_0"] = {"strikes": 3, "ban_remaining": 2}

        # First trip: should be banned (decrements to 1)
        eligible1 = strike_norm.is_eligible(context, "agent_0")
        assert eligible1 is False, "Should be banned on trip 1"

        # Second trip: should be banned (decrements to 0)
        eligible2 = strike_norm.is_eligible(context, "agent_0")
        assert eligible2 is False, "Should be banned on trip 2"

        # Third trip: should be eligible again (ban complete)
        eligible3 = strike_norm.is_eligible(context, "agent_0")
        assert eligible3 is True, "Should be eligible again after ban completes"

    def test_non_over_cap_sanction_does_not_count(self):
        """Only 'over_cap' sanctions should count as strikes."""
        strike_norm = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2
        })
        context = _context(stock_kg=100.0)

        # Different sanction type
        decision = NormDecision(kept_kg=10.0, sanction="some_other_violation", violated=True)
        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)

        assert "agent_0" not in context.norm_state("strike_ban"), \
            "Agent state should not be created for non-matching sanction"

    def test_no_violation_does_not_count(self):
        """Non-violations should not increment strike count."""
        strike_norm = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2
        })
        context = _context(stock_kg=100.0)

        # No violation
        decision = NormDecision(kept_kg=10.0, sanction=None, violated=False)
        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)

        assert "agent_0" not in context.norm_state("strike_ban"), \
            "Agent state should not be created when no violation"


class TestIntegration:
    """Integration tests for the full round 2 norm chain."""

    def test_full_violation_pipeline(self):
        """Test complete flow: catch_limit -> overage_penalty -> strike_ban."""
        context = _context(stock_kg=100.0)

        # Step 1: catch_limit limits 20kg to 12.5kg, marks as over_cap
        catch_limit = CatchLimitNorm(key="limit", params={"limit_pct_of_stock": 0.125})
        d1 = catch_limit.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=20.0)
        assert d1.kept_kg == 12.5
        assert d1.sanction == "over_cap"

        # Step 2: overage_penalty applies 50% penalty on 7.5kg overage
        penalty = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})
        d2 = penalty.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=d1.kept_kg)
        # 7.5kg overage * 50% = 3.75kg penalty
        # 12.5kg - 3.75kg = 8.75kg final
        assert d2.kept_kg == 8.75

        # Step 3: strike_ban counts the violation
        strike_ban = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2
        })
        final_decision = NormDecision(kept_kg=d2.kept_kg, sanction="over_cap", violated=True)
        strike_ban.on_agent_settled(context, "agent_0", final_decision, harvested_kg=d2.kept_kg)

        strikes = context.norm_state("strike_ban")["agent_0"]["strikes"]
        assert strikes == 1, f"Expected 1 strike, got {strikes}"

        # Verify fund has penalty
        fund = context.norm_state("penalty").get("community_fund", 0.0)
        assert fund == 3.75, f"Expected 3.75kg in fund, got {fund}"

    def test_clean_catch_no_penalty_no_strike(self):
        """Below-limit catch should have no penalty and no strike."""
        context = _context(stock_kg=100.0)

        # Catch 10kg (below 12.5kg limit)
        catch_limit = CatchLimitNorm(key="limit", params={"limit_pct_of_stock": 0.125})
        d1 = catch_limit.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
        assert d1.kept_kg == 10.0
        assert d1.violated is False
        assert d1.sanction is None

        # No penalty
        penalty = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})
        d2 = penalty.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=d1.kept_kg)
        assert d2.kept_kg == 10.0

        # No strike
        strike_ban = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2
        })
        final_decision = NormDecision(kept_kg=10.0, sanction=None, violated=False)
        strike_ban.on_agent_settled(context, "agent_0", final_decision, harvested_kg=10.0)

        assert "agent_0" not in context.norm_state("strike_ban")


class TestConfig:
    """Verify configuration matches requirements."""

    def test_config_has_catch_limit_with_12_5_pct(self):
        """Config should have catch_limit with limit_pct_of_stock=0.125."""
        with open("state/config.json") as f:
            config = json.load(f)

        catch_limits = [n for n in config.get("norms", []) if n.get("type") == "catch_limit"]
        assert len(catch_limits) >= 1, "Should have catch_limit norm"

        limit = catch_limits[0]
        assert limit.get("limit_pct_of_stock") == 0.125, \
            f"Expected limit_pct_of_stock=0.125, got {limit.get('limit_pct_of_stock')}"

    def test_config_has_overage_penalty_with_50_pct(self):
        """Config should have overage_penalty with penalty_pct=0.5."""
        with open("state/config.json") as f:
            config = json.load(f)

        penalties = [n for n in config.get("norms", []) if n.get("type") == "overage_penalty"]
        assert len(penalties) >= 1, "Should have overage_penalty norm"

        penalty = penalties[0]
        assert penalty.get("penalty_pct") == 0.5, \
            f"Expected penalty_pct=0.5, got {penalty.get('penalty_pct')}"

    def test_config_has_strike_ban_with_3_strikes_2_ban(self):
        """Config should have strike_ban with strikes=3 and ban_trips=2."""
        with open("state/config.json") as f:
            config = json.load(f)

        bans = [n for n in config.get("norms", []) if n.get("type") == "strike_ban"]
        assert len(bans) >= 1, "Should have strike_ban norm"

        ban = bans[0]
        assert ban.get("strikes") == 3, \
            f"Expected strikes=3, got {ban.get('strikes')}"
        assert ban.get("ban_trips") == 2, \
            f"Expected ban_trips=2, got {ban.get('ban_trips')}"

    def test_norms_are_in_correct_order(self):
        """Norms should be ordered: catch_limit -> overage_penalty -> strike_ban."""
        with open("state/config.json") as f:
            config = json.load(f)

        types = [n.get("type") for n in config.get("norms", [])]

        catch_idx = types.index("catch_limit")
        penalty_idx = types.index("overage_penalty")
        strike_idx = types.index("strike_ban")

        assert catch_idx < penalty_idx < strike_idx, \
            f"Norms should be in order catch_limit < overage_penalty < strike_ban, got indices {catch_idx}, {penalty_idx}, {strike_idx}"
