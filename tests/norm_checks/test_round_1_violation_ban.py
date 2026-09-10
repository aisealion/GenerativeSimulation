"""Tests for Round 1: Violation Handler and Repeated Violation Ban.

Policy: If a fisher violates >5kg or reserve <1kg, they return 2kg and get a reminder.
Repeated violations (2nd+) result in a one-week ban.
"""

import pytest

from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.violation_handler import ViolationHandlerNorm
from norms.repeated_violation_ban import RepeatedViolationBanNorm


def _context(stock_kg=300.0, round_number=1, existing_runtime=None):
    """Create a test context."""
    runtime = {"stock_kg": stock_kg, "rounds": []}
    if existing_runtime:
        runtime.update(existing_runtime)
    return HarvestContext.from_state({
        "config": {},
        "fluents": [],
        "runtime": runtime,
        "agents": {},
        "round_number": round_number,
    })


class TestViolationHandler:
    """Tests for the violation_handler norm."""

    def test_no_penalty_without_violation(self):
        """R4: No penalty applied when there's no violation."""
        norm = ViolationHandlerNorm(key="vh", params={})
        context = _context()
        decision = NormDecision.allow(kept_kg=4.0)

        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=4.0)

        state = context.norm_state("vh")
        assert state.get("communal_barrel_kg", 0.0) == 0.0
        assert state.get("violations", {}).get("agent_0", {}).get("count", 0) == 0

    def test_penalty_applied_for_over_cap(self):
        """R4: 2kg penalty added to communal barrel for over_cap violation."""
        norm = ViolationHandlerNorm(key="vh", params={"penalty_kg": 2.0})
        context = _context()
        decision = NormDecision.violation(kept_kg=5.0, sanction="over_cap", note="Over limit")

        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=5.0)

        state = context.norm_state("vh")
        assert state["communal_barrel_kg"] == 2.0
        assert state["violations"]["agent_0"]["count"] == 1

    def test_penalty_applied_for_under_reserve(self):
        """R4: 2kg penalty added for under_reserve violation."""
        norm = ViolationHandlerNorm(key="vh", params={"penalty_kg": 2.0})
        context = _context()
        decision = NormDecision.violation(kept_kg=0.5, sanction="under_reserve")

        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=0.5)

        state = context.norm_state("vh")
        assert state["communal_barrel_kg"] == 2.0
        assert state["violations"]["agent_0"]["count"] == 1

    def test_violation_count_accumulates(self):
        """R4: Multiple violations are counted."""
        norm = ViolationHandlerNorm(key="vh", params={})
        context = _context()

        # First violation
        decision1 = NormDecision.violation(kept_kg=5.0, sanction="over_cap")
        norm.on_agent_settled(context, "agent_0", decision1, harvested_kg=5.0)

        # Second violation
        decision2 = NormDecision.violation(kept_kg=5.0, sanction="over_cap")
        norm.on_agent_settled(context, "agent_0", decision2, harvested_kg=5.0)

        state = context.norm_state("vh")
        assert state["violations"]["agent_0"]["count"] == 2

    def test_ledger_entry_created(self):
        """R4: Violations are recorded in the ledger."""
        norm = ViolationHandlerNorm(key="vh", params={})
        context = _context(round_number=5)
        decision = NormDecision.violation(kept_kg=5.0, sanction="over_cap")

        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=5.0)

        state = context.norm_state("vh")
        ledger = state["ledger"]
        assert len(ledger) == 1
        assert ledger[0]["round"] == 5
        assert ledger[0]["agent_id"] == "agent_0"
        assert ledger[0]["transfer_kg"] == 2.0


class TestRepeatedViolationBan:
    """Tests for the repeated_violation_ban norm."""

    def test_eligible_with_no_violations(self):
        """R5: Agent is eligible with no violations."""
        norm = RepeatedViolationBanNorm(key="ban", params={})
        context = _context()

        assert norm.is_eligible(context, "agent_0") is True

    def test_eligible_with_one_violation(self):
        """R5: Agent is eligible with only 1 violation."""
        norm = RepeatedViolationBanNorm(key="ban", params={})
        # Pre-seed violation handler state with 1 violation
        runtime = {
            "norms": {
                "violation_handler": {
                    "violations": {
                        "agent_0": {"count": 1, "history": []}
                    }
                }
            }
        }
        context = _context(existing_runtime=runtime)

        # Ban is imposed in on_agent_settled, not is_eligible
        # So initially they should still be eligible
        assert norm.is_eligible(context, "agent_0") is True

    def test_ban_imposed_on_second_violation(self):
        """R5: Ban is imposed when violation count reaches threshold."""
        norm = RepeatedViolationBanNorm(key="ban", params={
            "violation_threshold": 2,
            "ban_duration_rounds": 7
        })
        # Pre-seed with 2 violations
        runtime = {
            "norms": {
                "violation_handler": {
                    "violations": {
                        "agent_0": {"count": 2, "history": [{}, {}]}
                    }
                }
            }
        }
        context = _context(round_number=5, existing_runtime=runtime)
        decision = NormDecision.allow(kept_kg=5.0)

        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=5.0)

        # Check ban was imposed
        state = context.norm_state("ban")
        # ban_start = round_number + 1 = 6
        # ban_end = ban_start + ban_duration_rounds - 1 = 6 + 7 - 1 = 12
        assert state["agent_0"]["banned_until_round"] == 12

    def test_banned_agent_is_ineligible(self):
        """R5: Banned agent is ineligible during ban period."""
        norm = RepeatedViolationBanNorm(key="ban", params={})
        runtime = {
            "norms": {
                "ban": {
                    "agent_0": {"banned_until_round": 10}
                }
            }
        }
        context = _context(round_number=5, existing_runtime=runtime)

        assert norm.is_eligible(context, "agent_0") is False

    def test_ban_expires_after_duration(self):
        """R5: Agent becomes eligible again after ban expires."""
        norm = RepeatedViolationBanNorm(key="ban", params={})
        runtime = {
            "norms": {
                "ban": {
                    "agent_0": {"banned_until_round": 10}
                }
            }
        }
        context = _context(round_number=11, existing_runtime=runtime)

        assert norm.is_eligible(context, "agent_0") is True

    def test_ban_describes_restriction(self):
        """R5: Ban provides description to banned agents."""
        norm = RepeatedViolationBanNorm(key="ban", params={})
        runtime = {
            "norms": {
                "ban": {
                    "agent_0": {"banned_until_round": 10}
                }
            }
        }
        context = _context(round_number=5, existing_runtime=runtime)

        description = norm.describe(context, "agent_0")
        assert description is not None
        assert "banned" in description.lower()
