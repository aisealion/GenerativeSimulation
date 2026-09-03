"""
Independent verification tests for Round 1 Norm Implementation.

Requirements from state/norm_specs/round_1.md:
- R1: Per-trip catch limit - Each fisher's kept catch for a single trip shall not exceed 10 kg.
- R2: Excess release - Any catch amount above 10 kg must be released (not kept).
- R3: Violation sanction - A fisher who exceeds the 10 kg limit receives a temporary fishing ban for exactly 1 subsequent trip.
"""

import pytest
from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.catch_limit import CatchLimitNorm
from norms.violation_ban import ViolationBanNorm


def _context(stock=300.0, round_number=1):
    """Create a HarvestContext for testing."""
    return HarvestContext.from_state({
        "config": {},
        "fluents": [],
        "runtime": {"stock_kg": stock},
        "agents": {},
        "round_number": round_number,
    })


class TestR1_PerTripCatchLimit:
    """R1: Each fisher's kept catch for a single trip shall not exceed 10 kg."""

    def test_catch_at_exactly_10kg_is_allowed(self):
        """A catch of exactly 10kg should be fully kept."""
        norm = CatchLimitNorm(key="catch_limit", params={"limit_kg": 10})
        decision = norm.evaluate(_context(), "agent_0", raw_kg=10.0, proposed_kg=10.0)
        assert decision.kept_kg == 10.0
        assert decision.violated is False

    def test_catch_below_10kg_is_allowed(self):
        """A catch below 10kg should be fully kept."""
        norm = CatchLimitNorm(key="catch_limit", params={"limit_kg": 10})
        decision = norm.evaluate(_context(), "agent_0", raw_kg=8.5, proposed_kg=8.5)
        assert decision.kept_kg == 8.5
        assert decision.violated is False

    def test_catch_above_10kg_is_limited(self):
        """A catch above 10kg should be reduced to 10kg."""
        norm = CatchLimitNorm(key="catch_limit", params={"limit_kg": 10})
        decision = norm.evaluate(_context(), "agent_0", raw_kg=15.0, proposed_kg=15.0)
        assert decision.kept_kg == 10.0
        assert decision.kept_kg <= 10.0  # R1 requirement

    def test_very_large_catch_is_limited_to_10kg(self):
        """Even very large catches should be limited to 10kg."""
        norm = CatchLimitNorm(key="catch_limit", params={"limit_kg": 10})
        decision = norm.evaluate(_context(), "agent_0", raw_kg=50.0, proposed_kg=50.0)
        assert decision.kept_kg == 10.0
        assert decision.kept_kg <= 10.0  # R1 requirement


class TestR2_ExcessRelease:
    """R2: Any catch amount above 10 kg must be released (not kept)."""

    def test_excess_amount_is_not_kept_15kg(self):
        """If raw_kg=15kg, kept should be 10kg and 5kg released."""
        norm = CatchLimitNorm(key="catch_limit", params={"limit_kg": 10})
        raw_kg = 15.0
        decision = norm.evaluate(_context(), "agent_0", raw_kg=raw_kg, proposed_kg=raw_kg)
        assert decision.kept_kg == 10.0
        assert decision.kept_kg < raw_kg  # Excess was released

    def test_excess_amount_is_not_kept_12kg(self):
        """If raw_kg=12kg, kept should be 10kg and 2kg released."""
        norm = CatchLimitNorm(key="catch_limit", params={"limit_kg": 10})
        raw_kg = 12.0
        decision = norm.evaluate(_context(), "agent_0", raw_kg=raw_kg, proposed_kg=raw_kg)
        assert decision.kept_kg == 10.0
        released_amount = raw_kg - decision.kept_kg
        assert released_amount == 2.0

    def test_violation_flag_is_set_on_excess(self):
        """When excess is caught, violated flag should be True."""
        norm = CatchLimitNorm(key="catch_limit", params={"limit_kg": 10})
        decision = norm.evaluate(_context(), "agent_0", raw_kg=15.0, proposed_kg=15.0)
        assert decision.violated is True
        assert decision.sanction == "over_cap"

    def test_no_violation_when_under_limit(self):
        """When under limit, violated flag should be False."""
        norm = CatchLimitNorm(key="catch_limit", params={"limit_kg": 10})
        decision = norm.evaluate(_context(), "agent_0", raw_kg=8.0, proposed_kg=8.0)
        assert decision.violated is False
        assert decision.sanction is None


class TestR3_ViolationSanctionTemporaryBan:
    """R3: After a violation, is_eligible(agent) returns False for exactly 1 subsequent round, then True again."""

    def test_matching_sanction_starts_1_trip_ban(self):
        """When sanction matches trigger_sanction, a 1-trip ban should start."""
        norm = ViolationBanNorm(
            key="violation_ban",
            params={"trigger_sanction": "over_cap", "trips": 1}
        )
        context = _context()
        decision = NormDecision(kept_kg=10.0, sanction="over_cap", violated=True)
        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
        
        # Ban state should show 1 trip remaining
        assert context.norm_state("violation_ban")["agent_0"]["trips_remaining"] == 1

    def test_ban_blocks_next_trip_only(self):
        """Exactly 1 subsequent trip should be blocked after a violation."""
        norm = ViolationBanNorm(
            key="violation_ban",
            params={"trigger_sanction": "over_cap", "trips": 1}
        )
        context = _context()
        
        # Simulate a violation
        decision = NormDecision(kept_kg=10.0, sanction="over_cap", violated=True)
        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
        
        # Next round (round 2): should be ineligible (banned)
        assert norm.is_eligible(context, "agent_0") is False
        
        # Round 3: should be eligible again
        assert norm.is_eligible(context, "agent_0") is True

    def test_no_ban_without_matching_sanction(self):
        """If sanction doesn't match trigger, no ban should be issued."""
        norm = ViolationBanNorm(
            key="violation_ban",
            params={"trigger_sanction": "over_cap", "trips": 1}
        )
        context = _context()
        decision = NormDecision(kept_kg=10.0, sanction="different_sanction", violated=True)
        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)
        
        # Should still be eligible
        assert norm.is_eligible(context, "agent_0") is True

    def test_agent_without_violation_remains_eligible(self):
        """Agents without violations should always be eligible."""
        norm = ViolationBanNorm(
            key="violation_ban",
            params={"trigger_sanction": "over_cap", "trips": 1}
        )
        context = _context()
        
        # No violation recorded
        assert norm.is_eligible(context, "agent_0") is True
        assert norm.is_eligible(context, "agent_0") is True


class TestRound1Integration:
    """Integration tests combining catch_limit and violation_ban for Round 1."""

    def test_full_violation_flow(self):
        """Test complete flow: exceed limit -> get sanctioned -> banned for 1 trip."""
        catch_limit = CatchLimitNorm(key="catch_limit", params={"limit_kg": 10})
        violation_ban = ViolationBanNorm(
            key="violation_ban",
            params={"trigger_sanction": "over_cap", "trips": 1}
        )
        context = _context()
        
        # Agent tries to catch 15kg
        raw_kg = 15.0
        
        # Step 1: Catch limit norm reduces to 10kg and marks violation
        decision = catch_limit.evaluate(context, "agent_0", raw_kg=raw_kg, proposed_kg=raw_kg)
        assert decision.kept_kg == 10.0
        assert decision.violated is True
        assert decision.sanction == "over_cap"
        
        # Step 2: Violation ban norm sees the sanction and starts ban
        violation_ban.on_agent_settled(context, "agent_0", decision, harvested_kg=decision.kept_kg)
        assert context.norm_state("violation_ban")["agent_0"]["trips_remaining"] == 1
        
        # Step 3: Next round, agent is ineligible
        assert violation_ban.is_eligible(context, "agent_0") is False
        
        # Step 4: Following round, agent is eligible again
        assert violation_ban.is_eligible(context, "agent_0") is True

    def test_no_violation_no_ban(self):
        """Test that compliant agents are never banned."""
        catch_limit = CatchLimitNorm(key="catch_limit", params={"limit_kg": 10})
        violation_ban = ViolationBanNorm(
            key="violation_ban",
            params={"trigger_sanction": "over_cap", "trips": 1}
        )
        context = _context()
        
        # Agent catches 8kg (under limit)
        raw_kg = 8.0
        decision = catch_limit.evaluate(context, "agent_0", raw_kg=raw_kg, proposed_kg=raw_kg)
        assert decision.kept_kg == 8.0
        assert decision.violated is False
        assert decision.sanction is None
        
        # No ban should be triggered
        violation_ban.on_agent_settled(context, "agent_0", decision, harvested_kg=decision.kept_kg)
        assert "agent_0" not in context.norm_state("violation_ban") or \
               context.norm_state("violation_ban").get("agent_0", {}).get("trips_remaining", 0) == 0
        
        # Agent remains eligible
        assert violation_ban.is_eligible(context, "agent_0") is True


class TestRound1Config:
    """Tests verifying the config matches Round 1 requirements."""

    def test_config_has_correct_norms(self):
        """Verify state/config.json has the correct norm configuration."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)
        
        # Should have catch_limit with 10kg limit
        catch_limit_norms = [n for n in config.get("norms", []) if n.get("type") == "catch_limit"]
        assert len(catch_limit_norms) >= 1, "Should have at least one catch_limit norm"
        
        catch_limit = catch_limit_norms[0]
        assert catch_limit.get("limit_kg") == 10, f"catch_limit should have limit_kg=10, got {catch_limit.get('limit_kg')}"
        
        # Should have violation_ban with correct parameters
        violation_ban_norms = [n for n in config.get("norms", []) if n.get("type") == "violation_ban"]
        assert len(violation_ban_norms) >= 1, "Should have at least one violation_ban norm"
        
        violation_ban = violation_ban_norms[0]
        assert violation_ban.get("trigger_sanction") == "over_cap", \
            f"violation_ban should trigger on 'over_cap', got {violation_ban.get('trigger_sanction')}"
        assert violation_ban.get("trips") == 1, \
            f"violation_ban should have trips=1, got {violation_ban.get('trips')}"

    def test_catch_limit_comes_before_violation_ban(self):
        """Verify catch_limit comes before violation_ban in config order."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)
        
        norm_types = [n.get("type") for n in config.get("norms", [])]
        
        if "catch_limit" in norm_types and "violation_ban" in norm_types:
            catch_idx = norm_types.index("catch_limit")
            ban_idx = norm_types.index("violation_ban")
            assert catch_idx < ban_idx, \
                f"catch_limit (index {catch_idx}) should come before violation_ban (index {ban_idx})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
