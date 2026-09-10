"""Tests for Round 2: Reserve Verification Norm.

Policy: The fisher's 1 kg reserve is weighed by the watcher before departure
and logged as "Reserve kept: 1 kg – verified by [watcher]"; any shortfall
forces the fisher to sit out the next trip.
"""

import pytest

from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.reserve_verification import ReserveVerificationNorm


def _context(stock_kg=300.0, round_number=1, existing_runtime=None, agents=None, fluents=None):
    """Create a test context."""
    runtime = {"stock_kg": stock_kg, "rounds": []}
    if existing_runtime:
        runtime.update(existing_runtime)
    return HarvestContext.from_state({
        "config": {},
        "fluents": fluents or [],
        "runtime": runtime,
        "agents": agents or {"agent_0": {"name": "Alice"}, "agent_1": {"name": "Bob", "role": "lake_watcher"}},
        "round_number": round_number,
    })


class TestReserveVerification:
    """Tests for the reserve_verification norm."""

    def test_passes_with_sufficient_reserve(self):
        """R5: Verification passes when reserve is sufficient."""
        norm = ReserveVerificationNorm(key="verify", params={"reserve_kg": 1.0})

        # Set up sufficient reserve
        runtime = {
            "norms": {
                "mandatory_reserve": {
                    "agent_0": {"reserve_kg": 1.0, "recorded": True}
                }
            },
            "stock_kg": 300.0,
            "rounds": []
        }
        context = _context(existing_runtime=runtime)

        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)

        assert not decision.violated
        assert "Reserve kept: 1kg" in decision.note

    def test_fails_with_shortfall(self):
        """R5: Verification fails when reserve is insufficient."""
        norm = ReserveVerificationNorm(key="verify", params={"reserve_kg": 1.0})

        # Set up insufficient reserve
        runtime = {
            "norms": {
                "mandatory_reserve": {
                    "agent_0": {"reserve_kg": 0.5, "recorded": True}
                }
            },
            "stock_kg": 300.0,
            "rounds": []
        }
        context = _context(existing_runtime=runtime)

        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)

        assert decision.violated
        assert decision.sanction == "reserve_shortfall"
        assert "sit out the next trip" in decision.note

    def test_verification_recorded(self):
        """R5: Verification result is recorded."""
        norm = ReserveVerificationNorm(key="verify", params={"reserve_kg": 1.0})

        runtime = {
            "norms": {
                "mandatory_reserve": {
                    "agent_0": {"reserve_kg": 1.0, "recorded": True}
                }
            },
            "stock_kg": 300.0,
            "rounds": []
        }
        context = _context(round_number=1, existing_runtime=runtime)

        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)

        state = context.norm_state("verify")
        verifications = state.get("verifications", [])
        assert len(verifications) == 1
        assert verifications[0]["agent_id"] == "agent_0"
        assert verifications[0]["passed"] is True
        assert verifications[0]["reserve_kg"] == 1.0

    def test_shortfall_tracked(self):
        """R5: Shortfall is tracked for ban enforcement."""
        norm = ReserveVerificationNorm(key="verify", params={"reserve_kg": 1.0})

        runtime = {
            "norms": {
                "mandatory_reserve": {
                    "agent_0": {"reserve_kg": 0.5, "recorded": True}
                }
            },
            "stock_kg": 300.0,
            "rounds": []
        }
        context = _context(round_number=1, existing_runtime=runtime)

        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)

        state = context.norm_state("verify")
        shortfalls = state.get("shortfalls", [])
        assert len(shortfalls) == 1
        assert shortfalls[0]["agent_id"] == "agent_0"
        assert shortfalls[0]["reason"] == "reserve_shortfall"

    def test_describes_verification_requirement(self):
        """R5: Norm describes the verification requirement."""
        norm = ReserveVerificationNorm(key="verify", params={"reserve_kg": 1.0})
        context = _context()

        description = norm.describe(context, "agent_0")

        assert "reserve" in description.lower()
        # Description should mention either verification or maintenance
        assert "verified" in description.lower() or "verification" in description.lower() or "maintained" in description.lower()

    def test_uses_watcher_for_verification(self):
        """R5: Verification is attributed to the lake-watcher."""
        norm = ReserveVerificationNorm(key="verify", params={"reserve_kg": 1.0})

        # Set up fluents with a lake_watcher role
        fluents = [
            {
                "fluent": "lake_watcher",
                "args": [],
                "holder": "agent_1",
                "initiated_round": 1,
                "terminated_round": None
            }
        ]
        runtime = {
            "norms": {
                "mandatory_reserve": {
                    "agent_0": {"reserve_kg": 1.0, "recorded": True}
                }
            },
            "stock_kg": 300.0,
            "rounds": []
        }
        context = _context(existing_runtime=runtime, fluents=fluents)

        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)

        assert "verified by" in decision.note.lower()
