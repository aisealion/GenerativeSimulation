"""
Independent Evaluator Tests for Round 1 Norm Implementation

Requirements from state/norm_specs/round_1.md:
- R1: harvested_kg(agent, trip) <= 15 for every fisher on every trip
- R2: Excess catch above 15kg is not kept (returned/rejected)
- R3: sum(harvested_kg(all_agents, round)) <= 100 for each round
- R4: When the community cap is reached, subsequent fishers receive 0kg
- R5: A fisher who exceeds the 15kg individual limit receives a temporary fishing ban
- R6: A fisher who catches when the community cap is already exhausted receives a temporary fishing ban
- R7: The ban duration is 2 trips
"""

import pytest
from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from engine.norms.registry import NORM_TYPES


def make_context(stock_before=300.0, round_number=1, existing_norm_state=None, scratch=None):
    """Create a HarvestContext for testing."""
    runtime = {"norms": existing_norm_state or {}}
    return HarvestContext(
        config={},
        fluents=[],
        runtime=runtime,
        agents={},
        round_number=round_number,
        stock_before=stock_before,
        scratch=scratch or {}
    )


class TestR1Individual15kgLimit:
    """Tests for R1: Individual catch limit of 15kg per trip."""

    def test_catch_limit_allows_under_limit(self):
        """R1: Catch at 15kg should be allowed."""
        CatchLimitNorm = NORM_TYPES["catch_limit"]
        norm = CatchLimitNorm(key="catch_limit", params={"limit_kg": 15})
        context = make_context()

        decision = norm.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=15.0)

        assert decision.kept_kg == 15.0, f"Expected 15kg allowed, got {decision.kept_kg}"
        assert not decision.violated, "Should not be a violation at exactly 15kg"

    def test_catch_limit_caps_at_15kg(self):
        """R1: Catch above 15kg should be capped."""
        CatchLimitNorm = NORM_TYPES["catch_limit"]
        norm = CatchLimitNorm(key="catch_limit", params={"limit_kg": 15})
        context = make_context()

        decision = norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)

        assert decision.kept_kg == 15.0, f"Expected capped at 15kg, got {decision.kept_kg}"
        assert decision.violated, "Should be marked as violation when capped"

    def test_catch_limit_allows_small_catches(self):
        """R1: Small catches should be allowed."""
        CatchLimitNorm = NORM_TYPES["catch_limit"]
        norm = CatchLimitNorm(key="catch_limit", params={"limit_kg": 15})
        context = make_context()

        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)

        assert decision.kept_kg == 5.0, f"Expected 5kg allowed, got {decision.kept_kg}"
        assert not decision.violated, "Should not be a violation for small catch"


class TestR2ExcessNotKept:
    """Tests for R2: Excess catch above 15kg is not kept."""

    def test_excess_catch_returned(self):
        """R2: When catching 25kg with 15kg limit, only 15kg is kept."""
        CatchLimitNorm = NORM_TYPES["catch_limit"]
        norm = CatchLimitNorm(key="catch_limit", params={"limit_kg": 15})
        context = make_context()

        decision = norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)

        assert decision.kept_kg == 15.0, f"Excess not returned: kept {decision.kept_kg} instead of 15kg"
        assert decision.violated, "Should be marked as violation"
        assert decision.sanction == "over_cap", f"Expected sanction 'over_cap', got {decision.sanction}"

    def test_excess_10kg_returned(self):
        """R2: When catching 20kg with 15kg limit, excess 5kg is returned."""
        CatchLimitNorm = NORM_TYPES["catch_limit"]
        norm = CatchLimitNorm(key="catch_limit", params={"limit_kg": 15})
        context = make_context()

        decision = norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=20.0)

        assert decision.kept_kg == 15.0, f"Expected 15kg kept, got {decision.kept_kg}"


class TestR3Community100kgCap:
    """Tests for R3: Community total catch must not exceed 100kg per round."""

    def test_community_cap_tracks_running_total(self):
        """R3: Community cap should track cumulative catch."""
        CommunityCapNorm = NORM_TYPES["community_cap"]
        norm = CommunityCapNorm(key="community_cap", params={"cap_kg": 100})
        context = make_context()

        # First agent catches 30kg
        decision1 = norm.evaluate(context, "agent_0", raw_kg=30.0, proposed_kg=30.0)
        assert decision1.kept_kg == 30.0, "First agent should get full 30kg"
        assert not decision1.violated, "First agent should not be in violation"

        # Second agent tries to catch 80kg (would exceed 100kg cap)
        decision2 = norm.evaluate(context, "agent_1", raw_kg=80.0, proposed_kg=80.0)
        assert decision2.kept_kg == 70.0, f"Expected capped at 70kg (100-30), got {decision2.kept_kg}"
        assert decision2.violated, "Should be violation when community cap hit"

    def test_community_cap_exactly_at_limit(self):
        """R3: When community total exactly at 100kg, subsequent get 0."""
        CommunityCapNorm = NORM_TYPES["community_cap"]
        norm = CommunityCapNorm(key="community_cap", params={"cap_kg": 100})
        context = make_context()

        # First agent catches exactly 100kg
        decision1 = norm.evaluate(context, "agent_0", raw_kg=100.0, proposed_kg=100.0)
        assert decision1.kept_kg == 100.0, "Should allow exactly 100kg"

        # Second agent should get 0
        decision2 = norm.evaluate(context, "agent_1", raw_kg=10.0, proposed_kg=10.0)
        assert decision2.kept_kg == 0.0, f"Expected 0kg when cap exhausted, got {decision2.kept_kg}"

    def test_community_cap_under_limit(self):
        """R3: When community total under 100kg, agents can catch."""
        CommunityCapNorm = NORM_TYPES["community_cap"]
        norm = CommunityCapNorm(key="community_cap", params={"cap_kg": 100})
        context = make_context()

        # Agent catches 50kg
        decision = norm.evaluate(context, "agent_0", raw_kg=50.0, proposed_kg=50.0)
        assert decision.kept_kg == 50.0, "Should allow 50kg"
        assert not decision.violated, "Should not be violation"


class TestR4SubsequentFishersGetZero:
    """Tests for R4: When community cap reached, subsequent fishers receive 0kg."""

    def test_subsequent_fishers_get_zero_when_cap_exhausted(self):
        """R4: After community cap reached, later fishers get 0."""
        CommunityCapNorm = NORM_TYPES["community_cap"]
        norm = CommunityCapNorm(key="community_cap", params={"cap_kg": 100})
        context = make_context()

        # Three agents try to catch 40kg each (total would be 120kg)
        decision1 = norm.evaluate(context, "agent_0", raw_kg=40.0, proposed_kg=40.0)
        assert decision1.kept_kg == 40.0, "First agent should get 40kg"

        decision2 = norm.evaluate(context, "agent_1", raw_kg=40.0, proposed_kg=40.0)
        assert decision2.kept_kg == 40.0, "Second agent should get 40kg"

        # Cap now at 80/100, third agent tries 40kg but only 20kg left
        decision3 = norm.evaluate(context, "agent_2", raw_kg=40.0, proposed_kg=40.0)
        assert decision3.kept_kg == 20.0, f"Expected 20kg remaining, got {decision3.kept_kg}"
        assert decision3.violated, "Should be violation when hitting cap"
        assert decision3.sanction == "over_community_cap", f"Expected 'over_community_cap', got {decision3.sanction}"

        # Fourth agent gets 0
        decision4 = norm.evaluate(context, "agent_3", raw_kg=30.0, proposed_kg=30.0)
        assert decision4.kept_kg == 0.0, f"Expected 0kg when cap exhausted, got {decision4.kept_kg}"
        assert decision4.violated, "Should be violation"
        assert decision4.sanction == "over_community_cap"


class TestR5BanForIndividualLimitViolation:
    """Tests for R5: Fisher exceeding 15kg limit receives temporary ban."""

    def test_over_cap_sanction_triggers_ban(self):
        """R5: Sanction 'over_cap' should trigger 2-trip ban."""
        ViolationBanNorm = NORM_TYPES["violation_ban"]
        norm = ViolationBanNorm(
            key="violation_ban",
            params={"trigger_sanction": ["over_cap", "over_community_cap"], "trips": 2}
        )
        context = make_context()

        # Simulate a violation decision
        violation_decision = NormDecision.violation(
            kept_kg=15,
            sanction="over_cap",
            note="Exceeded individual limit"
        )

        norm.on_agent_settled(context, "agent_0", violation_decision, 15.0)

        # Check ban was applied
        ban_state = context.norm_state("violation_ban")
        assert "agent_0" in ban_state, "Ban state should track agent_0"
        assert ban_state["agent_0"]["trips_remaining"] == 2, f"Expected 2-trip ban, got {ban_state['agent_0']['trips_remaining']}"


class TestR6BanForCommunityCapViolation:
    """Tests for R6: Fisher catching when community cap exhausted receives ban."""

    def test_over_community_cap_sanction_triggers_ban(self):
        """R6: Sanction 'over_community_cap' should trigger 2-trip ban."""
        ViolationBanNorm = NORM_TYPES["violation_ban"]
        norm = ViolationBanNorm(
            key="violation_ban",
            params={"trigger_sanction": ["over_cap", "over_community_cap"], "trips": 2}
        )
        context = make_context()

        # Simulate a community cap violation decision
        violation_decision = NormDecision.violation(
            kept_kg=0,
            sanction="over_community_cap",
            note="Community cap exhausted"
        )

        norm.on_agent_settled(context, "agent_1", violation_decision, 0.0)

        # Check ban was applied
        ban_state = context.norm_state("violation_ban")
        assert "agent_1" in ban_state, "Ban state should track agent_1 for community cap violation"
        assert ban_state["agent_1"]["trips_remaining"] == 2, f"Expected 2-trip ban, got {ban_state['agent_1']['trips_remaining']}"

    def test_both_sanction_types_trigger_ban(self):
        """R6: Both 'over_cap' and 'over_community_cap' should trigger bans."""
        ViolationBanNorm = NORM_TYPES["violation_ban"]
        norm = ViolationBanNorm(
            key="violation_ban",
            params={"trigger_sanction": ["over_cap", "over_community_cap"], "trips": 2}
        )
        context = make_context()

        # Test over_cap
        norm.on_agent_settled(context, "agent_a", NormDecision.violation(kept_kg=15, sanction="over_cap"), 15.0)
        # Test over_community_cap
        norm.on_agent_settled(context, "agent_b", NormDecision.violation(kept_kg=0, sanction="over_community_cap"), 0.0)

        ban_state = context.norm_state("violation_ban")
        assert ban_state["agent_a"]["trips_remaining"] == 2, "over_cap should trigger ban"
        assert ban_state["agent_b"]["trips_remaining"] == 2, "over_community_cap should trigger ban"


class TestR7BanDuration2Trips:
    """Tests for R7: Ban duration is 2 trips."""

    def test_ban_duration_is_2_trips(self):
        """R7: Ban should last exactly 2 trips."""
        ViolationBanNorm = NORM_TYPES["violation_ban"]
        norm = ViolationBanNorm(
            key="violation_ban",
            params={"trigger_sanction": ["over_cap"], "trips": 2}
        )
        context = make_context()

        # Trigger ban
        violation = NormDecision.violation(kept_kg=15, sanction="over_cap")
        norm.on_agent_settled(context, "agent_0", violation, 15.0)

        ban_state = context.norm_state("violation_ban")
        assert ban_state["agent_0"]["trips_remaining"] == 2

    def test_ban_countdown_decrements(self):
        """R7: Ban countdown should decrement each round until 0."""
        ViolationBanNorm = NORM_TYPES["violation_ban"]
        norm = ViolationBanNorm(
            key="violation_ban",
            params={"trigger_sanction": ["over_cap"], "trips": 2}
        )

        # Round 1: Agent has ban with 2 trips remaining
        context1 = make_context(existing_norm_state={"violation_ban": {"agent_0": {"trips_remaining": 2}}})

        # First call to is_eligible should decrement and return False (banned)
        eligible1 = norm.is_eligible(context1, "agent_0")
        assert not eligible1, "Should be ineligible with ban"

        ban_state1 = context1.norm_state("violation_ban")
        assert ban_state1["agent_0"]["trips_remaining"] == 1, f"Expected 1 trip remaining, got {ban_state1['agent_0']['trips_remaining']}"

        # Round 2: Ban should be 1, then decremented to 0
        context2 = make_context(existing_norm_state={"violation_ban": {"agent_0": {"trips_remaining": 1}}})

        eligible2 = norm.is_eligible(context2, "agent_0")
        assert not eligible2, "Should still be ineligible"

        ban_state2 = context2.norm_state("violation_ban")
        assert ban_state2["agent_0"]["trips_remaining"] == 0, f"Expected 0 trips remaining, got {ban_state2['agent_0']['trips_remaining']}"

        # Round 3: Ban should be 0, agent eligible
        context3 = make_context(existing_norm_state={"violation_ban": {"agent_0": {"trips_remaining": 0}}})

        eligible3 = norm.is_eligible(context3, "agent_0")
        assert eligible3, "Should be eligible after ban expires"

        ban_state3 = context3.norm_state("violation_ban")
        assert ban_state3["agent_0"]["trips_remaining"] == 0


class TestIntegration:
    """Integration tests for full norm chain."""

    def test_full_chain_individual_then_community(self):
        """Integration: Individual limit (15kg) applied, then community cap (100kg)."""
        CatchLimitNorm = NORM_TYPES["catch_limit"]
        CommunityCapNorm = NORM_TYPES["community_cap"]

        catch_limit = CatchLimitNorm(key="catch_limit", params={"limit_kg": 15})
        community_cap = CommunityCapNorm(key="community_cap", params={"cap_kg": 100})
        context = make_context()

        # Agent tries to catch 20kg
        # Step 1: Individual limit caps at 15kg
        decision1 = catch_limit.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=20.0)
        assert decision1.kept_kg == 15.0, f"Individual limit failed: got {decision1.kept_kg}"

        # Step 2: Community cap processes the 15kg (still under 100kg)
        decision2 = community_cap.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=15.0)
        assert decision2.kept_kg == 15.0, f"Community cap failed: got {decision2.kept_kg}"

    def test_full_chain_individual_violation_triggers_ban(self):
        """Integration: Individual violation -> sanction -> ban."""
        CatchLimitNorm = NORM_TYPES["catch_limit"]
        ViolationBanNorm = NORM_TYPES["violation_ban"]

        catch_limit = CatchLimitNorm(key="catch_limit", params={"limit_kg": 15})
        violation_ban = ViolationBanNorm(
            key="violation_ban",
            params={"trigger_sanction": ["over_cap", "over_community_cap"], "trips": 2}
        )
        context = make_context()

        # Agent catches 25kg, gets capped at 15kg with "over_cap" sanction
        decision = catch_limit.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)
        assert decision.sanction == "over_cap", f"Expected over_cap sanction, got {decision.sanction}"

        # Ban is triggered on settlement
        violation_ban.on_agent_settled(context, "agent_0", decision, decision.kept_kg)

        ban_state = context.norm_state("violation_ban")
        assert ban_state["agent_0"]["trips_remaining"] == 2, "Ban should be triggered"

    def test_full_chain_community_violation_triggers_ban(self):
        """Integration: Community cap violation -> sanction -> ban."""
        CommunityCapNorm = NORM_TYPES["community_cap"]
        ViolationBanNorm = NORM_TYPES["violation_ban"]

        community_cap = CommunityCapNorm(key="community_cap", params={"cap_kg": 100})
        violation_ban = ViolationBanNorm(
            key="violation_ban",
            params={"trigger_sanction": ["over_cap", "over_community_cap"], "trips": 2}
        )
        context = make_context()

        # Fill up community cap
        community_cap.evaluate(context, "agent_0", raw_kg=100.0, proposed_kg=100.0)

        # Next agent tries to catch and gets 0 with "over_community_cap" sanction
        decision = community_cap.evaluate(context, "agent_1", raw_kg=10.0, proposed_kg=10.0)
        assert decision.sanction == "over_community_cap", f"Expected over_community_cap sanction, got {decision.sanction}"

        # Ban is triggered
        violation_ban.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        ban_state = context.norm_state("violation_ban")
        assert ban_state["agent_1"]["trips_remaining"] == 2, "Ban should be triggered for community cap violation"


class TestConfig:
    """Tests for configuration validation."""

    def test_config_has_correct_norms(self):
        """Verify state/config.json has the required norms."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)

        norm_types = [n["type"] for n in config.get("norms", [])]
        assert "catch_limit" in norm_types, "Missing catch_limit norm"
        assert "community_cap" in norm_types, "Missing community_cap norm"
        assert "violation_ban" in norm_types, "Missing violation_ban norm"

    def test_config_catch_limit_params(self):
        """Verify catch_limit has limit_kg=15."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)

        catch_limit = next((n for n in config["norms"] if n["type"] == "catch_limit"), None)
        assert catch_limit is not None, "catch_limit not found"
        assert catch_limit.get("limit_kg") == 15, f"Expected limit_kg=15, got {catch_limit.get('limit_kg')}"

    def test_config_community_cap_params(self):
        """Verify community_cap has cap_kg=100."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)

        community_cap = next((n for n in config["norms"] if n["type"] == "community_cap"), None)
        assert community_cap is not None, "community_cap not found"
        assert community_cap.get("cap_kg") == 100, f"Expected cap_kg=100, got {community_cap.get('cap_kg')}"

    def test_config_violation_ban_params(self):
        """Verify violation_ban has correct trigger_sanction and trips."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)

        violation_ban = next((n for n in config["norms"] if n["type"] == "violation_ban"), None)
        assert violation_ban is not None, "violation_ban not found"
        assert violation_ban.get("trips") == 2, f"Expected trips=2, got {violation_ban.get('trips')}"

        trigger = violation_ban.get("trigger_sanction", [])
        assert "over_cap" in trigger, "Missing 'over_cap' in trigger_sanction"
        assert "over_community_cap" in trigger, "Missing 'over_community_cap' in trigger_sanction"

    def test_config_norm_order(self):
        """Verify norms are in correct order: catch_limit, community_cap, violation_ban."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)

        norm_types = [n["type"] for n in config.get("norms", [])]
        expected_order = ["catch_limit", "community_cap", "violation_ban"]
        assert norm_types == expected_order, f"Expected order {expected_order}, got {norm_types}"


class TestFourthWallCompliance:
    """Tests for fourth-wall compliance (no code terms in agent-facing text)."""

    def test_catch_limit_describe_no_code_terms(self):
        """catch_limit.describe() should not expose internal state keys."""
        CatchLimitNorm = NORM_TYPES["catch_limit"]
        norm = CatchLimitNorm(key="catch_limit", params={"limit_kg": 15})
        context = make_context()

        description = norm.describe(context, "agent_0")

        assert description is not None, "Should provide a description"
        assert "limit_kg" not in description, f"Description contains code term 'limit_kg': {description}"
        assert "agent_0" not in description, f"Description contains agent_id: {description}"
        assert "15" in description, f"Description should mention 15kg: {description}"

    def test_community_cap_describe_no_code_terms(self):
        """community_cap.describe() should not expose internal state keys."""
        CommunityCapNorm = NORM_TYPES["community_cap"]
        norm = CommunityCapNorm(key="community_cap", params={"cap_kg": 100})
        context = make_context()

        description = norm.describe(context, "agent_0")

        assert description is not None, "Should provide a description"
        assert "cap_kg" not in description, f"Description contains code term 'cap_kg': {description}"
        assert "total_kg" not in description, f"Description contains internal key 'total_kg': {description}"

    def test_violation_ban_describe_no_code_terms(self):
        """violation_ban.describe() should not expose internal state keys."""
        ViolationBanNorm = NORM_TYPES["violation_ban"]
        norm = ViolationBanNorm(key="violation_ban", params={"trigger_sanction": ["over_cap"], "trips": 2})
        context = make_context(existing_norm_state={"violation_ban": {"agent_0": {"trips_remaining": 2}}})

        description = norm.describe(context, "agent_0")

        assert description is not None, "Should provide a description for banned agent"
        assert "trips_remaining" not in description, f"Description contains code term 'trips_remaining': {description}"
        assert "trigger_sanction" not in description, f"Description contains code term 'trigger_sanction': {description}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
