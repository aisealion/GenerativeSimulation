"""
Test to verify that community_cap violations trigger the violation_ban.

This test checks if there's a mismatch between:
- community_cap emits sanction: "over_community_cap"
- violation_ban triggers on: "over_cap"

If they don't match, R6 (community cap violators get banned) won't work.
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


class TestSanctionMatching:
    """Verify that sanctions from catch_limit and community_cap both trigger the ban."""

    def test_catch_limit_sanction_is_over_cap(self):
        """Verify catch_limit emits 'over_cap' sanction."""
        context = make_context(stock_before=300.0)
        CatchLimit = NORM_TYPES["catch_limit"]
        norm = CatchLimit(key="catch_limit", params={"limit_kg": 15})

        decision = norm.evaluate(context, "agent_0", raw_kg=30.0, proposed_kg=30.0)

        assert decision.sanction == "over_cap", f"catch_limit should emit 'over_cap', got '{decision.sanction}'"

    def test_community_cap_sanction_is_over_community_cap(self):
        """Verify community_cap emits 'over_community_cap' sanction (not 'over_cap')."""
        context = make_context(stock_before=300.0)
        CommunityCap = NORM_TYPES["community_cap"]
        norm = CommunityCap(key="community_cap", params={"cap_kg": 100})

        # Exhaust the cap with first agent
        decision1 = norm.evaluate(context, "agent_0", raw_kg=100.0, proposed_kg=100.0)
        assert decision1.kept_kg == 100.0

        # Second agent tries to catch when cap is exhausted
        decision2 = norm.evaluate(context, "agent_1", raw_kg=10.0, proposed_kg=10.0)

        # This is the actual sanction name emitted
        assert decision2.sanction == "over_community_cap", f"community_cap should emit 'over_community_cap', got '{decision2.sanction}'"

    def test_violation_ban_triggers_on_over_cap(self):
        """Verify violation_ban triggers on 'over_cap' (from catch_limit)."""
        context = make_context(stock_before=300.0)
        ViolationBan = NORM_TYPES["violation_ban"]
        norm = ViolationBan(key="violation_ban", params={"trigger_sanction": "over_cap", "trips": 2})

        violation = NormDecision.violation(kept_kg=15, sanction="over_cap", note="Over limit")
        norm.on_agent_settled(context, "agent_0", violation, 15.0)

        ban_state = context.norm_state("violation_ban")
        assert ban_state["agent_0"]["trips_remaining"] == 2, "Ban should trigger on 'over_cap'"

    def test_violation_ban_does_NOT_trigger_on_over_community_cap(self):
        """
        CRITICAL: violation_ban does NOT trigger on 'over_community_cap' when configured for 'over_cap'.
        This means R6 (community cap violators get banned) is NOT satisfied!
        """
        context = make_context(stock_before=300.0)
        ViolationBan = NORM_TYPES["violation_ban"]
        norm = ViolationBan(key="violation_ban", params={"trigger_sanction": "over_cap", "trips": 2})

        # Community cap violation emits 'over_community_cap'
        violation = NormDecision.violation(kept_kg=0, sanction="over_community_cap", note="Cap exhausted")
        norm.on_agent_settled(context, "agent_0", violation, 0.0)

        ban_state = context.norm_state("violation_ban")
        # Ban state may not even have agent_0, or trips_remaining might be 0/default
        trips_remaining = ban_state.get("agent_0", {}).get("trips_remaining", 0)

        # This assertion demonstrates the issue: the ban is NOT set
        assert trips_remaining == 0, f"CRITICAL: Ban NOT triggered for 'over_community_cap' (config expects 'over_cap'). trips_remaining={trips_remaining}"

    def test_current_config_will_not_ban_community_violators(self):
        """
        Test with the actual config from state/config.json to prove R6 is broken.
        """
        import json
        with open("state/config.json") as f:
            config = json.load(f)

        ban_config = next(n for n in config["norms"] if n["type"] == "violation_ban")
        trigger_sanction = ban_config.get("trigger_sanction")

        # The config expects 'over_cap'
        assert trigger_sanction == "over_cap", f"Config trigger is '{trigger_sanction}'"

        # But community_cap emits 'over_community_cap'
        context = make_context(stock_before=300.0)
        CommunityCap = NORM_TYPES["community_cap"]
        community_norm = CommunityCap(key="community_cap", params={"cap_kg": 100})

        # Exhaust cap
        community_norm.evaluate(context, "agent_0", raw_kg=100.0, proposed_kg=100.0)
        # Next agent violates
        decision = community_norm.evaluate(context, "agent_1", raw_kg=10.0, proposed_kg=10.0)

        # The sanction emitted is 'over_community_cap', not 'over_cap'
        assert decision.sanction == "over_community_cap"

        # Now try to apply the ban with the config settings
        ViolationBan = NORM_TYPES["violation_ban"]
        ban_norm = ViolationBan(key="violation_ban", params=ban_config)

        ban_norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        # Check if ban was applied
        ban_state = context.norm_state("violation_ban")
        agent_ban = ban_state.get("agent_1", {}).get("trips_remaining", 0)

        # This will be 0 because 'over_community_cap' != 'over_cap'
        assert agent_ban == 0, f"FAIL: Community cap violator NOT banned! trips_remaining={agent_ban}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
