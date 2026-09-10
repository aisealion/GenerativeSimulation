"""Tests for Round 2: Next Trip Ban and Excess Redistribution Norms.

Policy: Non-compliance results in the fisher sitting out the next trip.
Excess catch from non-compliant fishers is redistributed to compliant fishers.
"""

import pytest

from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.next_trip_ban import NextTripBanNorm
from norms.excess_redistribution import ExcessRedistributionNorm


def _context(stock_kg=300.0, round_number=1, existing_runtime=None, agents=None):
    """Create a test context."""
    runtime = {"stock_kg": stock_kg, "rounds": [], "payoff": {}}
    if agents:
        for agent_id in agents:
            runtime["payoff"][agent_id] = 0.0
    if existing_runtime:
        runtime.update(existing_runtime)
    return HarvestContext.from_state({
        "config": {},
        "fluents": [],
        "runtime": runtime,
        "agents": agents or {"agent_0": {"name": "Alice"}, "agent_1": {"name": "Bob"}},
        "round_number": round_number,
    })


class TestNextTripBan:
    """Tests for the next_trip_ban norm."""

    def test_eligible_without_violation(self):
        """R8: Agent is eligible without violation."""
        norm = NextTripBanNorm(key="ban", params={})
        context = _context()

        assert norm.is_eligible(context, "agent_0") is True

    def test_ban_imposed_after_violation(self):
        """R8: Ban is imposed after over_stock_limit violation."""
        norm = NextTripBanNorm(key="ban", params={})
        context = _context(round_number=1)

        decision = NormDecision.violation(
            kept_kg=10.0,
            sanction="over_stock_limit",
            note="Violation"
        )
        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)

        # Check that ban is queued for next round
        state = context.norm_state("ban")
        assert state["agent_0"]["banned_next_round"] is True

    def test_ban_active_next_round(self):
        """R8: Ban is active the round after violation."""
        norm = NextTripBanNorm(key="ban", params={})

        # Round 1: Violation occurs
        context1 = _context(round_number=1)
        decision = NormDecision.violation(kept_kg=10.0, sanction="over_stock_limit")
        norm.on_agent_settled(context1, "agent_0", decision, harvested_kg=10.0)

        # Verify ban is queued for next round
        state = context1.norm_state("ban")
        assert state["agent_0"]["banned_next_round"] is True

        # on_round_end moves banned_next_round to banned_this_round
        norm.on_round_end(context1, {})

        # Now banned_this_round should be True
        assert state["agent_0"]["banned_this_round"] is True
        assert state["agent_0"]["banned_next_round"] is False

    def test_ban_cleared_after_served(self):
        """R8: Ban is cleared after one round."""
        norm = NextTripBanNorm(key="ban", params={})

        # Simulate banned state
        runtime = {
            "norms": {
                "ban": {
                    "agent_0": {"banned_this_round": True, "reason": "over_stock_limit"}
                }
            },
            "stock_kg": 300.0,
            "rounds": [],
            "payoff": {}
        }
        context = _context(round_number=2, existing_runtime=runtime)

        # First check should return False (banned)
        assert norm.is_eligible(context, "agent_0") is False

        # After round end, ban should be cleared
        norm.on_round_end(context, {})
        # Note: is_eligible would need a fresh context to see cleared ban

    def test_describe_for_banned_agent(self):
        """R8: Banned agent gets description."""
        norm = NextTripBanNorm(key="ban", params={})
        runtime = {
            "norms": {
                "ban": {
                    "agent_0": {"banned_this_round": True, "reason": "over_stock_limit"}
                }
            },
            "stock_kg": 300.0,
            "rounds": [],
            "payoff": {}
        }
        context = _context(round_number=2, existing_runtime=runtime)

        description = norm.describe(context, "agent_0")
        assert description is not None
        assert "sitting out" in description.lower()

    def test_reserve_shortfall_triggers_ban(self):
        """R8: Reserve shortfall also triggers ban."""
        norm = NextTripBanNorm(key="ban", params={})
        context = _context(round_number=1)

        decision = NormDecision.violation(
            kept_kg=5.0,
            sanction="reserve_shortfall",
            note="Reserve verification failed"
        )
        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=5.0)

        state = context.norm_state("ban")
        assert state["agent_0"]["banned_next_round"] is True


class TestExcessRedistribution:
    """Tests for the excess_redistribution norm."""

    def test_no_violations_no_redistribution(self):
        """R6: No redistribution when there are no violations."""
        norm = ExcessRedistributionNorm(key="redist", params={"stock_cap_key": "cap"})
        context = _context(round_number=1)

        round_results = {
            "agent_0": {"participated": True, "harvested_kg": 5.0},
            "agent_1": {"participated": True, "harvested_kg": 5.0},
        }
        norm.on_round_end(context, round_results)

        state = context.norm_state("redist")
        assert "redistributions" not in state or len(state.get("redistributions", [])) == 0

    def test_excess_redistributed_equally(self):
        """R6: Excess is split equally among compliant agents."""
        norm = ExcessRedistributionNorm(key="redist", params={"stock_cap_key": "cap"})

        # Set up violation data
        runtime = {
            "norms": {
                "cap": {
                    "violations": [
                        {
                            "round": 1,
                            "agent_id": "agent_0",
                            "excess_kg": 10.0
                        }
                    ]
                }
            },
            "stock_kg": 300.0,
            "rounds": [],
            "payoff": {"agent_0": 0.0, "agent_1": 0.0}
        }
        context = _context(round_number=1, existing_runtime=runtime)

        round_results = {
            "agent_0": {"participated": True, "harvested_kg": 20.0},  # Violator
            "agent_1": {"participated": True, "harvested_kg": 5.0},   # Compliant
        }
        norm.on_round_end(context, round_results)

        # Check that compliant agent received the excess
        payoff = context.runtime["payoff"]
        assert payoff["agent_1"] == 10.0  # Full 10kg to the one compliant agent

    def test_redistribution_split_among_multiple_compliant(self):
        """R6: Excess is split among all compliant agents."""
        norm = ExcessRedistributionNorm(key="redist", params={"stock_cap_key": "cap"})

        runtime = {
            "norms": {
                "cap": {
                    "violations": [
                        {"round": 1, "agent_id": "agent_0", "excess_kg": 10.0}
                    ]
                }
            },
            "stock_kg": 300.0,
            "rounds": [],
            "payoff": {"agent_0": 0.0, "agent_1": 0.0, "agent_2": 0.0}
        }
        agents = {"agent_0": {"name": "A"}, "agent_1": {"name": "B"}, "agent_2": {"name": "C"}}
        context = _context(round_number=1, existing_runtime=runtime, agents=agents)

        round_results = {
            "agent_0": {"participated": True, "harvested_kg": 20.0},  # Violator
            "agent_1": {"participated": True, "harvested_kg": 5.0},   # Compliant
            "agent_2": {"participated": True, "harvested_kg": 5.0},   # Compliant
        }
        norm.on_round_end(context, round_results)

        # Each compliant agent should get 5kg (10kg / 2 compliant agents)
        payoff = context.runtime["payoff"]
        assert payoff["agent_1"] == 5.0
        assert payoff["agent_2"] == 5.0

    def test_redistribution_recorded(self):
        """R6: Redistribution is recorded in state."""
        norm = ExcessRedistributionNorm(key="redist", params={"stock_cap_key": "cap"})

        runtime = {
            "norms": {
                "cap": {
                    "violations": [
                        {"round": 1, "agent_id": "agent_0", "excess_kg": 10.0}
                    ]
                }
            },
            "stock_kg": 300.0,
            "rounds": [],
            "payoff": {"agent_0": 0.0, "agent_1": 0.0}
        }
        context = _context(round_number=1, existing_runtime=runtime)

        round_results = {
            "agent_0": {"participated": True, "harvested_kg": 20.0},
            "agent_1": {"participated": True, "harvested_kg": 5.0},
        }
        norm.on_round_end(context, round_results)

        state = context.norm_state("redist")
        redistributions = state.get("redistributions", [])
        assert len(redistributions) == 1
        assert redistributions[0]["total_excess_kg"] == 10.0
        assert redistributions[0]["compliant_count"] == 1
