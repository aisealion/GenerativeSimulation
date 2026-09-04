"""Tests for Round 3 weekly audit norm."""

import pytest
from engine.norms.context import HarvestContext
from norms.weekly_audit import WeeklyAuditNorm


class TestWeeklyAudit:
    """Test cases for the weekly audit norm."""

    def create_context(self, round_number=1, config=None, ledger=None):
        """Create a test HarvestContext."""
        if config is None:
            config = {
                "norms": [
                    {"type": "weekly_audit", "audit_frequency_rounds": 7, "audit_sample_rate": 0.30, "sanction_duration_rounds": 1},
                    {"type": "dynamic_individual_cap", "id": "cap_norm"}
                ]
            }

        runtime = {"norms": {}}

        # Pre-populate ledger if provided
        if ledger:
            runtime["norms"]["cap_norm"] = {"ledger": ledger}

        return HarvestContext(
            config=config,
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=round_number,
            stock_before=50.0,
        )

    def test_audit_on_correct_round(self):
        """Audit occurs on the correct round (multiple of 7)."""
        # Round 7 should trigger audit
        # Create ledger showing agent_1 exceeded cap in round 5
        ledger = [
            {"round": 5, "agent_id": "agent_1", "raw_catch": 20.0, "kept": 15.0, "returned": 5.0, "cap_applied": 15},
            {"round": 5, "agent_id": "agent_2", "raw_catch": 10.0, "kept": 10.0, "returned": 0.0, "cap_applied": 15},
        ]
        context = self.create_context(round_number=7, ledger=ledger)
        norm = WeeklyAuditNorm(key="weekly_audit", params={})

        round_results = {
            "agent_1": {"harvested_kg": 10.0, "effort": 1.0, "participated": True, "note": None},
            "agent_2": {"harvested_kg": 10.0, "effort": 1.0, "participated": True, "note": None},
        }

        norm.on_round_end(context, round_results)

        # Check that audit history was recorded
        audit_history = context.norm_state("weekly_audit").get("audit_history", [])
        assert len(audit_history) == 1
        assert audit_history[0]["round"] == 7

    def test_no_audit_on_wrong_round(self):
        """No audit on non-audit rounds."""
        # Round 5 should not trigger audit
        context = self.create_context(round_number=5)
        norm = WeeklyAuditNorm(key="weekly_audit", params={})

        round_results = {
            "agent_1": {"harvested_kg": 10.0, "effort": 1.0, "participated": True, "note": None},
        }

        norm.on_round_end(context, round_results)

        audit_history = context.norm_state("weekly_audit").get("audit_history", [])
        assert len(audit_history) == 0

    def test_is_eligible_no_ban(self):
        """Agent is eligible when no ban is active."""
        context = self.create_context()
        norm = WeeklyAuditNorm(key="weekly_audit", params={})

        assert norm.is_eligible(context, "agent_1") is True

    def test_is_eligible_with_ban(self):
        """Agent is not eligible when ban is active."""
        context = self.create_context()
        norm = WeeklyAuditNorm(key="weekly_audit", params={})

        # Set up a pending ban
        norm_state = context.norm_state("weekly_audit")
        norm_state["pending_bans"] = {"agent_1": 1}

        assert norm.is_eligible(context, "agent_1") is False

    def test_ban_decrements(self):
        """Ban counter decrements after use."""
        context = self.create_context()
        norm = WeeklyAuditNorm(key="weekly_audit", params={})

        # Set up a pending ban
        norm_state = context.norm_state("weekly_audit")
        norm_state["pending_bans"] = {"agent_1": 1}

        # First check should return False and clear the ban
        assert norm.is_eligible(context, "agent_1") is False

        # Second check should return True (ban cleared)
        assert norm.is_eligible(context, "agent_1") is True

    def test_describe_shows_ban(self):
        """Description indicates when agent is banned."""
        context = self.create_context()
        norm = WeeklyAuditNorm(key="weekly_audit", params={})

        # Set up a pending ban
        norm_state = context.norm_state("weekly_audit")
        norm_state["pending_bans"] = {"agent_1": 1}

        description = norm.describe(context, "agent_1")

        assert "BANNED" in description
        assert "fishing rights" in description.lower()

    def test_describe_shows_audit_results(self):
        """Description shows audit results from previous round."""
        context = self.create_context(round_number=8)
        norm = WeeklyAuditNorm(key="weekly_audit", params={})

        # Set up audit history from round 7
        norm_state = context.norm_state("weekly_audit")
        norm_state["audit_history"] = [{
            "round": 7,
            "audited_agents": ["agent_1"],
            "sanctioned_agents": ["agent_1"],
            "violations": [],
            "total_agents": 2,
        }]

        description = norm.describe(context, "agent_1")

        assert "AUDIT RESULTS" in description
        assert "agent_1" in description

    def test_describe_shows_upcoming_audit(self):
        """Description warns of upcoming audit."""
        # Round 6 - audit tomorrow (round 7)
        context = self.create_context(round_number=6)
        norm = WeeklyAuditNorm(key="weekly_audit", params={})

        description = norm.describe(context, "agent_1")

        assert "AUDIT TOMORROW" in description or "audit" in description.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
