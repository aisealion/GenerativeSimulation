"""Round 2 verification tests - validates the 12.5% limit + penalty + 3-strike ban implementation."""

import json
import pytest

from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from engine.norms.registry import load_norms
from norms.catch_limit import CatchLimitNorm
from norms.overage_penalty import OveragePenaltyNorm
from norms.strike_ban import StrikeBanNorm


class TestR1_PercentageBasedCatchLimit:
    """R1: Each fisher's kept catch shall not exceed 12.5% of current lake biomass."""

    def test_catch_at_12_5_pct_is_allowed(self):
        """Catch at exactly 12.5% of stock should be allowed."""
        norm = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        context = HarvestContext.from_state({
            "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
            "agents": {}, "round_number": 1,
        })

        # 12.5% of 100 = 12.5 kg
        decision = norm.evaluate(context, "agent_0", raw_kg=12.5, proposed_kg=12.5)
        assert decision.kept_kg == 12.5
        assert decision.violated is False

    def test_catch_below_12_5_pct_is_allowed(self):
        """Catch below 12.5% of stock should be allowed."""
        norm = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        context = HarvestContext.from_state({
            "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
            "agents": {}, "round_number": 1,
        })

        decision = norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
        assert decision.kept_kg == 10.0
        assert decision.violated is False

    def test_catch_above_12_5_pct_is_limited(self):
        """Catch above 12.5% of stock should be limited to 12.5%."""
        norm = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        context = HarvestContext.from_state({
            "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
            "agents": {}, "round_number": 1,
        })

        # Try to catch 20kg, limited to 12.5kg
        decision = norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=20.0)
        assert decision.kept_kg == 12.5
        assert decision.violated is True

    def test_limit_scales_with_biomass(self):
        """Limit should scale with current biomass."""
        norm = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})

        # At 200kg stock
        context = HarvestContext.from_state({
            "config": {}, "fluents": [], "runtime": {"stock_kg": 200.0},
            "agents": {}, "round_number": 1,
        })
        decision = norm.evaluate(context, "agent_0", raw_kg=100.0, proposed_kg=100.0)
        # 12.5% of 200 = 25 kg
        assert decision.kept_kg == 25.0

        # At 80kg stock
        context = HarvestContext.from_state({
            "config": {}, "fluents": [], "runtime": {"stock_kg": 80.0},
            "agents": {}, "round_number": 1,
        })
        decision = norm.evaluate(context, "agent_0", raw_kg=100.0, proposed_kg=100.0)
        # 12.5% of 80 = 10 kg
        assert decision.kept_kg == 10.0


class TestR2_ExcessRelease:
    """R2: Any catch above 12.5% must be released."""

    def test_excess_is_not_kept_20kg_raw(self):
        """Excess above limit is not kept."""
        norm = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        context = HarvestContext.from_state({
            "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
            "agents": {}, "round_number": 1,
        })

        decision = norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=20.0)
        # Only 12.5kg kept, 7.5kg released
        assert decision.kept_kg == 12.5

    def test_violation_flag_set_on_excess(self):
        """Violation flag should be set when excess is released."""
        norm = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        context = HarvestContext.from_state({
            "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
            "agents": {}, "round_number": 1,
        })

        decision = norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=20.0)
        assert decision.violated is True
        assert decision.sanction == "over_cap"


class TestR3_PenaltyForOverage:
    """R3: Penalty equal to 50% of overage paid to community."""

    def test_penalty_is_50_percent_of_overage(self):
        """Penalty should be 50% of the overage amount."""
        penalty_norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})
        context = HarvestContext.from_state({
            "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
            "agents": {}, "round_number": 1,
        })

        # Agent tried 20kg, was limited to 12.5kg
        # Overage = 20 - 12.5 = 7.5kg
        # Penalty = 50% of 7.5 = 3.75kg
        # Final kept = 12.5 - 3.75 = 8.75kg
        decision = penalty_norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=12.5)
        assert decision.kept_kg == 8.75

    def test_penalty_tracked_in_community_fund(self):
        """Penalty amount should be tracked in community fund."""
        penalty_norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})
        context = HarvestContext.from_state({
            "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
            "agents": {}, "round_number": 1,
        })

        penalty_norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=12.5)

        # Check community fund has the penalty
        fund = context.norm_state("penalty").get("community_fund", 0.0)
        assert fund == 3.75  # 50% of 7.5kg overage

    def test_note_explains_penalty(self):
        """Decision should include explanatory note about penalty."""
        penalty_norm = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})
        context = HarvestContext.from_state({
            "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
            "agents": {}, "round_number": 1,
        })

        decision = penalty_norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=12.5)
        assert "penalty" in decision.note.lower()
        assert "50%" in decision.note


class TestR4_ThreeStrikeBan:
    """R4: Ban after three violations."""

    def test_strike_count_tracked(self):
        """Each violation should increment strike count."""
        strike_norm = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2
        })
        context = HarvestContext.from_state({
            "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
            "agents": {}, "round_number": 1,
        })

        decision = NormDecision(kept_kg=10.0, sanction="over_cap", violated=True)

        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
        assert context.norm_state("strike_ban")["agent_0"]["strikes"] == 1

        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
        assert context.norm_state("strike_ban")["agent_0"]["strikes"] == 2

    def test_ban_triggered_after_three_strikes(self):
        """Ban should trigger after exactly three strikes."""
        strike_norm = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2
        })
        context = HarvestContext.from_state({
            "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
            "agents": {}, "round_number": 1,
        })

        decision = NormDecision(kept_kg=10.0, sanction="over_cap", violated=True)

        # First 2 strikes - no ban
        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
        assert context.norm_state("strike_ban")["agent_0"]["ban_remaining"] == 0
        assert strike_norm.is_eligible(context, "agent_0") is True

        # Third strike triggers ban
        strike_norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
        assert context.norm_state("strike_ban")["agent_0"]["ban_remaining"] == 2

    def test_ban_blocks_subsequent_trips(self):
        """Banned agent should be ineligible for subsequent trips."""
        strike_norm = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2
        })
        context = HarvestContext.from_state({
            "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
            "agents": {}, "round_number": 1,
        })

        # Set up banned state
        context.norm_state("strike_ban")["agent_0"] = {"strikes": 3, "ban_remaining": 2}

        # Should be banned for next 2 trips
        assert strike_norm.is_eligible(context, "agent_0") is False  # Trip 1 of ban
        assert strike_norm.is_eligible(context, "agent_0") is False  # Trip 2 of ban
        assert strike_norm.is_eligible(context, "agent_0") is True   # Ban complete


class TestRound2Integration:
    """Integration tests for round 2 norm composition."""

    def test_full_violation_flow(self):
        """Test the full flow: catch_limit -> overage_penalty -> strike_ban."""
        context = HarvestContext.from_state({
            "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
            "agents": {}, "round_number": 1,
        })

        # 1. catch_limit reduces 20kg to 12.5kg limit
        catch_limit = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        decision1 = catch_limit.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=20.0)
        assert decision1.kept_kg == 12.5
        assert decision1.sanction == "over_cap"

        # 2. overage_penalty calculates 50% penalty on 7.5kg overage
        penalty = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})
        decision2 = penalty.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=decision1.kept_kg)
        assert decision2.kept_kg == 8.75  # 12.5 - 3.75 penalty

        # 3. strike_ban counts the violation
        strike_ban = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2
        })

        # Create final decision with sanction
        final_decision = NormDecision(
            kept_kg=decision2.kept_kg,
            sanction="over_cap",
            violated=True,
            note="Violation occurred"
        )
        strike_ban.on_agent_settled(context, "agent_0", final_decision, harvested_kg=final_decision.kept_kg)

        assert context.norm_state("strike_ban")["agent_0"]["strikes"] == 1

    def test_no_violation_no_penalty_no_strike(self):
        """Clean catch below limit should have no penalty or strike."""
        context = HarvestContext.from_state({
            "config": {}, "fluents": [], "runtime": {"stock_kg": 100.0},
            "agents": {}, "round_number": 1,
        })

        # Catch 10kg (below 12.5kg limit)
        catch_limit = CatchLimitNorm(key="catch_limit", params={"limit_pct_of_stock": 0.125})
        decision1 = catch_limit.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
        assert decision1.kept_kg == 10.0
        assert decision1.violated is False

        # No penalty applied
        penalty = OveragePenaltyNorm(key="penalty", params={"penalty_pct": 0.5})
        decision2 = penalty.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=decision1.kept_kg)
        assert decision2.kept_kg == 10.0

        # No strike counted
        strike_ban = StrikeBanNorm(key="strike_ban", params={
            "trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2
        })
        final_decision = NormDecision(kept_kg=10.0, sanction=None, violated=False)
        strike_ban.on_agent_settled(context, "agent_0", final_decision, harvested_kg=10.0)

        assert "agent_0" not in context.norm_state("strike_ban")


class TestRound2Config:
    """Verify state/config.json has correct round 2 configuration."""

    def test_config_has_correct_norms(self):
        """Verify state/config.json has the correct norm configuration."""
        with open("state/config.json") as f:
            config = json.load(f)

        norms = config.get("norms", [])

        # Should have catch_limit with 12.5% limit
        catch_limit_norms = [n for n in norms if n.get("type") == "catch_limit"]
        assert len(catch_limit_norms) >= 1, "Should have at least one catch_limit norm"

        catch_limit = catch_limit_norms[0]
        assert catch_limit.get("limit_pct_of_stock") == 0.125, \
            f"catch_limit should have limit_pct_of_stock=0.125, got {catch_limit.get('limit_pct_of_stock')}"

        # Should have overage_penalty
        penalty_norms = [n for n in norms if n.get("type") == "overage_penalty"]
        assert len(penalty_norms) >= 1, "Should have at least one overage_penalty norm"

        penalty = penalty_norms[0]
        assert penalty.get("penalty_pct") == 0.5, \
            f"overage_penalty should have penalty_pct=0.5, got {penalty.get('penalty_pct')}"

        # Should have strike_ban
        strike_ban_norms = [n for n in norms if n.get("type") == "strike_ban"]
        assert len(strike_ban_norms) >= 1, "Should have at least one strike_ban norm"

        strike_ban = strike_ban_norms[0]
        assert strike_ban.get("strikes") == 3, \
            f"strike_ban should have strikes=3, got {strike_ban.get('strikes')}"
        assert strike_ban.get("ban_trips") == 2, \
            f"strike_ban should have ban_trips=2, got {strike_ban.get('ban_trips')}"

    def test_norms_in_correct_order(self):
        """catch_limit -> overage_penalty -> strike_ban."""
        with open("state/config.json") as f:
            config = json.load(f)

        norms = config.get("norms", [])
        type_order = [n.get("type") for n in norms]

        # Verify order
        catch_idx = type_order.index("catch_limit")
        penalty_idx = type_order.index("overage_penalty")
        strike_idx = type_order.index("strike_ban")

        assert catch_idx < penalty_idx, "catch_limit should come before overage_penalty"
        assert penalty_idx < strike_idx, "overage_penalty should come before strike_ban"

    def test_config_loads_without_errors(self):
        """Config should be loadable by the norm registry."""
        with open("state/config.json") as f:
            config = json.load(f)

        # This should not raise
        norms = load_norms(config)

        # Should have all three norm types
        type_names = [type(n).__name__ for n in norms]
        assert "CatchLimitNorm" in type_names
        assert "OveragePenaltyNorm" in type_names
        assert "StrikeBanNorm" in type_names
