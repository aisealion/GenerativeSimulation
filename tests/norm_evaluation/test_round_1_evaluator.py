"""
Round 1 Norm Evaluator Tests - Independent verification

These tests independently verify that the Round 1 norm implementation satisfies
all requirements from state/norm_specs/round_1.md:

- R1: harvested_kg(agent, trip) <= 15 for every fisher on every trip
- R2: Excess catch above 15kg is not kept (returned/rejected)
- R3: sum(harvested_kg(all_agents, round)) <= 100 for each round
- R4: When the community cap is reached, subsequent fishers receive 0kg
- R5: A fisher exceeding 15kg limit receives a temporary fishing ban
- R6: A fisher catching when community cap exhausted receives a temporary ban
- R7: The ban duration is 2 trips
"""

import pytest
from engine.norms.context import HarvestContext
from engine.norms.registry import NORM_TYPES
from engine.norms.base import NormDecision


def make_context(stock_before=300.0, round_number=1, existing_norm_state=None):
    """Create a HarvestContext for testing."""
    runtime = {"norms": existing_norm_state or {}}
    return HarvestContext(
        config={},
        fluents=[],
        runtime=runtime,
        agents={},
        round_number=round_number,
        stock_before=stock_before,
        scratch={}
    )


class TestR1_Individual15kgLimit:
    """Verify R1: Individual catch <= 15kg per trip."""

    def test_catch_under_limit_allowed(self):
        """Fisher catching 10kg (under 15kg limit) should be allowed full amount."""
        context = make_context(stock_before=300.0)
        CatchLimit = NORM_TYPES["catch_limit"]
        norm = CatchLimit(key="catch_limit", params={"limit_kg": 15})

        decision = norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)

        assert decision.kept_kg == 10.0, f"Should keep full 10kg, got {decision.kept_kg}"
        assert not decision.violated, "Should not be a violation"
        assert decision.sanction is None, "Should have no sanction"

    def test_catch_at_limit_allowed(self):
        """Fisher catching exactly 15kg should be allowed full amount."""
        context = make_context(stock_before=300.0)
        CatchLimit = NORM_TYPES["catch_limit"]
        norm = CatchLimit(key="catch_limit", params={"limit_kg": 15})

        decision = norm.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=15.0)

        assert decision.kept_kg == 15.0, f"Should keep full 15kg, got {decision.kept_kg}"
        assert not decision.violated, "Should not be a violation"

    def test_catch_over_limit_capped(self):
        """R1/R2: Fisher catching 20kg should be capped at 15kg."""
        context = make_context(stock_before=300.0)
        CatchLimit = NORM_TYPES["catch_limit"]
        norm = CatchLimit(key="catch_limit", params={"limit_kg": 15})

        decision = norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=20.0)

        assert decision.kept_kg == 15.0, f"Should be capped at 15kg, got {decision.kept_kg}"
        assert decision.violated, "Should be marked as violation"
        assert decision.sanction == "over_cap", f"Should have 'over_cap' sanction, got {decision.sanction}"

    def test_catch_way_over_limit_capped(self):
        """Fisher catching 50kg should still be capped at 15kg."""
        context = make_context(stock_before=500.0)
        CatchLimit = NORM_TYPES["catch_limit"]
        norm = CatchLimit(key="catch_limit", params={"limit_kg": 15})

        decision = norm.evaluate(context, "agent_0", raw_kg=50.0, proposed_kg=50.0)

        assert decision.kept_kg == 15.0, f"Should be capped at 15kg, got {decision.kept_kg}"
        assert decision.violated, "Should be marked as violation"


class TestR3R4_Community100kgCap:
    """Verify R3: Community total <= 100kg, and R4: subsequent fishers get 0kg."""

    def test_community_cap_allows_within_limit(self):
        """First fisher catching 30kg should be allowed (under 100kg cap)."""
        context = make_context(stock_before=300.0)
        CommunityCap = NORM_TYPES["community_cap"]
        norm = CommunityCap(key="community_cap", params={"cap_kg": 100})

        decision = norm.evaluate(context, "agent_0", raw_kg=30.0, proposed_kg=30.0)

        assert decision.kept_kg == 30.0, f"Should keep 30kg, got {decision.kept_kg}"
        assert not decision.violated, "Should not be a violation"

    def test_community_cap_tracks_running_total(self):
        """Community cap should track cumulative catch across agents."""
        context = make_context(stock_before=300.0)
        CommunityCap = NORM_TYPES["community_cap"]
        norm = CommunityCap(key="community_cap", params={"cap_kg": 100})

        # First agent catches 40kg
        decision1 = norm.evaluate(context, "agent_0", raw_kg=40.0, proposed_kg=40.0)
        assert decision1.kept_kg == 40.0

        # Second agent catches 40kg (total 80kg, still under 100kg)
        decision2 = norm.evaluate(context, "agent_1", raw_kg=40.0, proposed_kg=40.0)
        assert decision2.kept_kg == 40.0

        # Third agent tries 30kg (would exceed 100kg), only gets 20kg
        decision3 = norm.evaluate(context, "agent_2", raw_kg=30.0, proposed_kg=30.0)
        assert decision3.kept_kg == 20.0, f"Should be capped at 20kg, got {decision3.kept_kg}"

    def test_r4_subsequent_fishers_get_zero_when_cap_exhausted(self):
        """R4: When cap is reached, subsequent fishers receive 0kg."""
        context = make_context(stock_before=300.0)
        CommunityCap = NORM_TYPES["community_cap"]
        norm = CommunityCap(key="community_cap", params={"cap_kg": 100})

        # First agent catches 100kg (exhausts cap)
        decision1 = norm.evaluate(context, "agent_0", raw_kg=100.0, proposed_kg=100.0)
        assert decision1.kept_kg == 100.0

        # Second agent tries to catch anything - should get 0kg
        decision2 = norm.evaluate(context, "agent_1", raw_kg=50.0, proposed_kg=50.0)
        assert decision2.kept_kg == 0.0, f"Should get 0kg when cap exhausted, got {decision2.kept_kg}"
        assert decision2.violated, "Should be marked as violation when cap exhausted"

    def test_r3_community_total_never_exceeds_100kg(self):
        """R3: Sum of all catches must never exceed 100kg."""
        context = make_context(stock_before=500.0)
        CommunityCap = NORM_TYPES["community_cap"]
        norm = CommunityCap(key="community_cap", params={"cap_kg": 100})

        total_catch = 0.0
        agents = ["agent_0", "agent_1", "agent_2", "agent_3", "agent_4"]

        for agent_id in agents:
            decision = norm.evaluate(context, agent_id, raw_kg=30.0, proposed_kg=30.0)
            total_catch += decision.kept_kg
            assert total_catch <= 100.0, f"Total catch {total_catch} exceeded 100kg limit"

        assert total_catch == 100.0, f"Total should equal 100kg, got {total_catch}"


class TestR5R6R7_ViolationBan:
    """Verify R5, R6: Violators get ban; R7: Ban lasts 2 trips."""

    def test_r5_individual_violator_gets_ban(self):
        """R5: Fisher exceeding 15kg individual limit receives 2-trip ban."""
        context = make_context(stock_before=300.0)
        ViolationBan = NORM_TYPES["violation_ban"]
        norm = ViolationBan(key="violation_ban", params={"trigger_sanction": "over_cap", "trips": 2})

        # Simulate violation decision from catch_limit
        violation = NormDecision.violation(kept_kg=15, sanction="over_cap", note="Over limit")
        norm.on_agent_settled(context, "agent_0", violation, harvested_kg=15.0)

        ban_state = context.norm_state("violation_ban")
        assert "agent_0" in ban_state, "Violator should be in ban state"
        assert ban_state["agent_0"]["trips_remaining"] == 2, f"Ban should be 2 trips, got {ban_state['agent_0']['trips_remaining']}"

    def test_r6_community_cap_violator_gets_ban(self):
        """R6: Fisher catching when community cap exhausted gets 2-trip ban."""
        context = make_context(stock_before=300.0)
        ViolationBan = NORM_TYPES["violation_ban"]
        norm = ViolationBan(key="violation_ban", params={"trigger_sanction": "over_community_cap", "trips": 2})

        # Simulate violation decision from community_cap
        violation = NormDecision.violation(kept_kg=0, sanction="over_community_cap", note="Cap exhausted")
        norm.on_agent_settled(context, "agent_1", violation, harvested_kg=0.0)

        ban_state = context.norm_state("violation_ban")
        assert "agent_1" in ban_state, "Violator should be in ban state"
        assert ban_state["agent_1"]["trips_remaining"] == 2

    def test_r7_ban_duration_is_2_trips(self):
        """R7: Verify ban duration is exactly 2 trips."""
        context = make_context(stock_before=300.0)
        ViolationBan = NORM_TYPES["violation_ban"]
        norm = ViolationBan(key="violation_ban", params={"trigger_sanction": "over_cap", "trips": 2})

        # Set ban for agent
        violation = NormDecision.violation(kept_kg=15, sanction="over_cap")
        norm.on_agent_settled(context, "agent_0", violation, harvested_kg=15.0)

        # Verify initial ban is 2 trips
        ban_state = context.norm_state("violation_ban")
        assert ban_state["agent_0"]["trips_remaining"] == 2

    def test_banned_agent_is_ineligible(self):
        """Banned agent should be ineligible to fish."""
        context = make_context(stock_before=300.0, existing_norm_state={
            "violation_ban": {"agent_0": {"trips_remaining": 2}}
        })
        ViolationBan = NORM_TYPES["violation_ban"]
        norm = ViolationBan(key="violation_ban", params={"trigger_sanction": "over_cap", "trips": 2})

        assert not norm.is_eligible(context, "agent_0"), "Banned agent should be ineligible"
        assert norm.is_eligible(context, "agent_1"), "Non-banned agent should be eligible"

    def test_ban_countdown_decrements_each_round(self):
        """Ban countdown should decrement each round agent tries to fish."""
        # Start with 2 trips remaining
        context = make_context(stock_before=300.0, existing_norm_state={
            "violation_ban": {"agent_0": {"trips_remaining": 2}}
        })
        ViolationBan = NORM_TYPES["violation_ban"]
        norm = ViolationBan(key="violation_ban", params={"trigger_sanction": "over_cap", "trips": 2})

        # First check - should be ineligible and decrement to 1
        eligible = norm.is_eligible(context, "agent_0")
        assert not eligible, "Should be ineligible with 2 trips remaining"
        assert context.norm_state("violation_ban")["agent_0"]["trips_remaining"] == 1

    def test_ban_expires_after_2_rounds(self):
        """Ban should expire after being ineligible for 2 rounds."""
        # Start with 1 trip remaining (after one round of being banned)
        context = make_context(stock_before=300.0, existing_norm_state={
            "violation_ban": {"agent_0": {"trips_remaining": 1}}
        })
        ViolationBan = NORM_TYPES["violation_ban"]
        norm = ViolationBan(key="violation_ban", params={"trigger_sanction": "over_cap", "trips": 2})

        # Check eligibility - should decrement to 0 and become eligible
        eligible = norm.is_eligible(context, "agent_0")
        assert not eligible, "Should still be ineligible with 1 trip remaining"
        assert context.norm_state("violation_ban")["agent_0"]["trips_remaining"] == 0

        # Next round - should be eligible now
        context2 = make_context(stock_before=300.0, existing_norm_state={
            "violation_ban": {"agent_0": {"trips_remaining": 0}}
        })
        eligible = norm.is_eligible(context2, "agent_0")
        assert eligible, "Should be eligible with 0 trips remaining"


class TestIntegration_NormChaining:
    """Test that norms chain correctly: catch_limit -> community_cap -> violation_ban"""

    def test_individual_limit_applied_before_community_cap(self):
        """Catch limit should be applied first, then community cap."""
        context = make_context(stock_before=300.0)

        CatchLimit = NORM_TYPES["catch_limit"]
        CommunityCap = NORM_TYPES["community_cap"]

        catch_norm = CatchLimit(key="catch_limit", params={"limit_kg": 15})
        community_norm = CommunityCap(key="community_cap", params={"cap_kg": 100})

        # Agent tries to catch 50kg
        # Step 1: catch_limit caps at 15kg
        decision1 = catch_norm.evaluate(context, "agent_0", raw_kg=50.0, proposed_kg=50.0)
        assert decision1.kept_kg == 15.0

        # Step 2: community_cap receives the capped amount (15kg)
        decision2 = community_norm.evaluate(context, "agent_0", raw_kg=50.0, proposed_kg=decision1.kept_kg)
        assert decision2.kept_kg == 15.0, "Community cap should allow the already-capped amount"

    def test_ban_triggers_on_over_cap_sanction(self):
        """Violation ban should trigger when sanction is 'over_cap'."""
        context = make_context(stock_before=300.0)

        CatchLimit = NORM_TYPES["catch_limit"]
        ViolationBan = NORM_TYPES["violation_ban"]

        catch_norm = CatchLimit(key="catch_limit", params={"limit_kg": 15})
        ban_norm = ViolationBan(key="violation_ban", params={"trigger_sanction": "over_cap", "trips": 2})

        # Agent exceeds limit
        decision = catch_norm.evaluate(context, "agent_0", raw_kg=30.0, proposed_kg=30.0)
        assert decision.sanction == "over_cap", "Catch limit should emit 'over_cap' sanction"

        # Ban should trigger
        ban_norm.on_agent_settled(context, "agent_0", decision, decision.kept_kg)

        ban_state = context.norm_state("violation_ban")
        assert ban_state["agent_0"]["trips_remaining"] == 2, "Ban should be triggered"


class TestFourthWallCompliance:
    """Verify fourth-wall compliance: no internal state keys in agent-facing text."""

    def test_catch_limit_describe_no_internal_terms(self):
        """catch_limit describe() should not expose internal terms."""
        context = make_context(stock_before=300.0)
        CatchLimit = NORM_TYPES["catch_limit"]
        norm = CatchLimit(key="catch_limit", params={"limit_kg": 15})

        description = norm.describe(context, "agent_0")

        assert description is not None, "Should provide a description"
        # Check for absence of code-like terms
        internal_terms = ["limit_kg", "params", "config", "runtime", "agent_id", "None"]
        for term in internal_terms:
            assert term not in description, f"Description should not contain internal term '{term}': {description}"

    def test_community_cap_describe_no_internal_terms(self):
        """community_cap describe() should not expose internal terms."""
        context = make_context(stock_before=300.0)
        CommunityCap = NORM_TYPES["community_cap"]
        norm = CommunityCap(key="community_cap", params={"cap_kg": 100})

        description = norm.describe(context, "agent_0")

        assert description is not None, "Should provide a description"
        internal_terms = ["cap_kg", "params", "config", "runtime", "scratch", "None"]
        for term in internal_terms:
            assert term not in description, f"Description should not contain internal term '{term}': {description}"

    def test_violation_ban_describe_no_internal_terms(self):
        """violation_ban describe() should not expose internal terms."""
        context = make_context(stock_before=300.0, existing_norm_state={
            "violation_ban": {"agent_0": {"trips_remaining": 2}}
        })
        ViolationBan = NORM_TYPES["violation_ban"]
        norm = ViolationBan(key="violation_ban", params={"trigger_sanction": "over_cap", "trips": 2})

        description = norm.describe(context, "agent_0")

        assert description is not None, "Should provide a description when banned"
        internal_terms = ["trips_remaining", "params", "config", "runtime", "norm_state", "None"]
        for term in internal_terms:
            assert term not in description, f"Description should not contain internal term '{term}': {description}"


class TestConfigSpecification:
    """Verify the config matches the specification exactly."""

    def test_config_has_all_three_norms(self):
        """Config must include catch_limit, community_cap, and violation_ban."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)

        norm_types = [n["type"] for n in config.get("norms", [])]
        assert "catch_limit" in norm_types, "Config must have catch_limit"
        assert "community_cap" in norm_types, "Config must have community_cap"
        assert "violation_ban" in norm_types, "Config must have violation_ban"

    def test_catch_limit_is_15kg(self):
        """catch_limit must be set to 15kg."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)

        catch_limit = next(n for n in config["norms"] if n["type"] == "catch_limit")
        assert catch_limit.get("limit_kg") == 15, f"Individual limit must be 15kg, got {catch_limit.get('limit_kg')}"

    def test_community_cap_is_100kg(self):
        """community_cap must be set to 100kg."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)

        community_cap = next(n for n in config["norms"] if n["type"] == "community_cap")
        assert community_cap.get("cap_kg") == 100, f"Community cap must be 100kg, got {community_cap.get('cap_kg')}"

    def test_violation_ban_is_2_trips(self):
        """violation_ban must be set to 2 trips."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)

        ban = next(n for n in config["norms"] if n["type"] == "violation_ban")
        assert ban.get("trips") == 2, f"Ban must be 2 trips, got {ban.get('trips')}"
        assert ban.get("trigger_sanction") == "over_cap", f"Trigger must be 'over_cap', got {ban.get('trigger_sanction')}"

    def test_norm_order_is_correct(self):
        """Norms must be in order: catch_limit -> community_cap -> violation_ban."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)

        norm_types = [n["type"] for n in config.get("norms", [])]
        expected_order = ["catch_limit", "community_cap", "violation_ban"]
        assert norm_types == expected_order, f"Norm order must be {expected_order}, got {norm_types}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
