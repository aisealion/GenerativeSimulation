"""Independent integration tests for Round 2 norm implementation.

These tests verify the integration between multiple norms and edge cases
that might not be covered by individual norm tests.
"""

import pytest

from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.lake_watcher import LakeWatcherNorm
from norms.percent_stock_cap import PercentStockCapNorm
from norms.reserve_verification import ReserveVerificationNorm
from norms.next_trip_ban import NextTripBanNorm
from norms.excess_redistribution import ExcessRedistributionNorm


def _context(stock_kg=300.0, round_number=1, existing_runtime=None, agents=None, fluents=None):
    """Create a test context."""
    runtime = {"stock_kg": stock_kg, "rounds": [], "payoff": {}}
    if agents:
        for agent_id in agents:
            runtime["payoff"][agent_id] = 0.0
    if existing_runtime:
        runtime.update(existing_runtime)
    return HarvestContext.from_state({
        "config": {},
        "fluents": fluents or [],
        "runtime": runtime,
        "agents": agents or {"agent_0": {"name": "Alice"}, "agent_1": {"name": "Bob"}},
        "round_number": round_number,
    })


class TestNormIntegration:
    """Integration tests across multiple norms."""

    def test_config_norm_order(self):
        """Verify norms are configured in correct evaluation order."""
        import json
        import os

        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "state", "config.json")
        with open(config_path) as f:
            config = json.load(f)
        norm_types = [n["type"] for n in config["norms"]]

        # Required order per spec:
        # 1. lake_watcher - First, to establish stock estimate
        # 2. percent_stock_cap - Apply 10% stock-based cap
        # 3. mandatory_reserve - Check reserve compliance
        # 4. reserve_verification - Verify reserve with watcher
        # 5. next_trip_ban - Check eligibility
        # 6. excess_redistribution - Final redistribution

        # Verify lake_watcher comes before percent_stock_cap
        watcher_idx = next((i for i, t in enumerate(norm_types) if t == "lake_watcher"), None)
        cap_idx = next((i for i, t in enumerate(norm_types) if t == "percent_stock_cap"), None)

        assert watcher_idx is not None, "lake_watcher norm must be configured"
        assert cap_idx is not None, "percent_stock_cap norm must be configured"
        assert watcher_idx < cap_idx, "lake_watcher must come before percent_stock_cap"

    def test_all_required_norms_configured(self):
        """Verify all required norms from the spec are configured."""
        import json
        import os

        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "state", "config.json")
        with open(config_path) as f:
            config = json.load(f)
        norm_types = set(n["type"] for n in config["norms"])

        required_norms = {
            "lake_watcher",
            "percent_stock_cap",
            "mandatory_reserve",
            "reserve_verification",
            "next_trip_ban",
            "excess_redistribution",
        }

        missing = required_norms - norm_types
        assert not missing, f"Missing required norms: {missing}"

    def test_institution_norm_types_registered(self):
        """Verify all norm types are registered in institution.json."""
        import json
        import os

        institution_path = os.path.join(os.path.dirname(__file__), "..", "..", "state", "institution.json")
        with open(institution_path) as f:
            institution = json.load(f)

        registered_types = set(institution.get("norm_types", {}).keys())

        required_types = {
            "lake_watcher",
            "percent_stock_cap",
            "reserve_verification",
            "next_trip_ban",
            "excess_redistribution",
        }

        missing = required_types - registered_types
        assert not missing, f"Missing registered norm types: {missing}"

    def test_norm_files_exist(self):
        """Verify all norm implementation files exist."""
        import os

        norms_dir = os.path.join(os.path.dirname(__file__), "..", "..", "norms")
        required_files = {
            "lake_watcher.py",
            "percent_stock_cap.py",
            "reserve_verification.py",
            "next_trip_ban.py",
            "excess_redistribution.py",
        }

        for filename in required_files:
            filepath = os.path.join(norms_dir, filename)
            assert os.path.exists(filepath), f"Missing norm file: {filename}"


class TestLakeWatcherEdgeCases:
    """Edge cases for lake_watcher norm."""

    def test_watcher_skipped_if_already_assigned(self):
        """Verify watcher is not reassigned if one already exists for this round."""
        norm = LakeWatcherNorm(key="watcher", params={})

        # Pre-assign a watcher via fluents
        fluents = [{
            "fluent": "lake_watcher",
            "args": [],
            "holder": "agent_0",
            "initiated_round": 1,
            "terminated_round": None
        }]

        context = _context(round_number=1, fluents=fluents, agents={
            "agent_0": {"name": "Alice"},
            "agent_1": {"name": "Bob"}
        })

        state_before = context.norm_state("watcher").copy()
        norm.on_round_start(context)

        # Should keep the same watcher
        watcher = norm.get_current_watcher(context)
        assert watcher == "agent_0"

    def test_stock_estimate_with_zero_stock(self):
        """Verify behavior when stock is at zero."""
        norm = LakeWatcherNorm(key="watcher", params={})
        context = _context(stock_kg=0.0, round_number=1)

        norm.on_round_start(context)

        state = context.norm_state("watcher")
        assert state["current_estimate_kg"] == 0.0

    def test_watcher_exclusion_of_dead_agents(self):
        """Verify dead agents are not selected as watchers."""
        norm = LakeWatcherNorm(key="watcher", params={})

        runtime = {
            "stock_kg": 300.0,
            "rounds": [],
            "dead_agents": ["agent_0"],
            "payoff": {}
        }
        agents = {"agent_0": {"name": "DeadAgent"}, "agent_1": {"name": "AliveAgent"}}

        context = _context(round_number=1, existing_runtime=runtime, agents=agents)
        norm.on_round_start(context)

        watcher = norm.get_current_watcher(context)
        assert watcher == "agent_1"  # Should select the alive agent


class TestPercentStockCapEdgeCases:
    """Edge cases for percent_stock_cap norm."""

    def test_zero_stock_estimate(self):
        """Verify behavior when stock estimate is zero."""
        norm = PercentStockCapNorm(key="cap", params={"percent_limit": 0.10})
        context = _context(stock_kg=0.0, round_number=1)

        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)

        # With 0 stock, limit is 0, so any catch is a violation
        assert decision.kept_kg == 0.0
        assert decision.violated

    def test_very_small_stock(self):
        """Verify rounding behavior with very small stock."""
        norm = PercentStockCapNorm(key="cap", params={"percent_limit": 0.10})
        runtime = {
            "norms": {"lake_watcher": {"current_estimate_kg": 1.0}},
            "stock_kg": 1.0,
            "rounds": [],
            "payoff": {}
        }
        context = _context(round_number=1, existing_runtime=runtime)

        decision = norm.evaluate(context, "agent_0", raw_kg=0.5, proposed_kg=0.5)

        # 10% of 1kg = 0.1kg limit, so 0.5kg should be trimmed
        assert decision.kept_kg == 0.1
        assert decision.violated

    def test_custom_percentage_limit(self):
        """Verify norm works with different percentage limits."""
        norm = PercentStockCapNorm(key="cap", params={"percent_limit": 0.25})
        runtime = {
            "norms": {"lake_watcher": {"current_estimate_kg": 100.0}},
            "stock_kg": 100.0,
            "rounds": [],
            "payoff": {}
        }
        context = _context(round_number=1, existing_runtime=runtime)

        decision = norm.evaluate(context, "agent_0", raw_kg=30.0, proposed_kg=30.0)

        # 25% of 100kg = 25kg limit
        assert decision.kept_kg == 25.0


class TestReserveVerificationEdgeCases:
    """Edge cases for reserve_verification norm."""

    def test_exactly_at_reserve_requirement(self):
        """Verify pass when reserve exactly equals requirement."""
        norm = ReserveVerificationNorm(key="verify", params={"reserve_kg": 1.0})

        runtime = {
            "norms": {"mandatory_reserve": {"agent_0": {"reserve_kg": 1.0}}},
            "stock_kg": 300.0,
            "rounds": [],
            "payoff": {}
        }
        context = _context(existing_runtime=runtime)

        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)

        assert not decision.violated

    def test_zero_reserve(self):
        """Verify violation when reserve is zero."""
        norm = ReserveVerificationNorm(key="verify", params={"reserve_kg": 1.0})

        runtime = {
            "norms": {"mandatory_reserve": {"agent_0": {"reserve_kg": 0.0}}},
            "stock_kg": 300.0,
            "rounds": [],
            "payoff": {}
        }
        context = _context(existing_runtime=runtime)

        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)

        assert decision.violated
        assert decision.sanction == "reserve_shortfall"


class TestNextTripBanEdgeCases:
    """Edge cases for next_trip_ban norm."""

    def test_multiple_violations_same_round(self):
        """Verify ban is imposed even with multiple violations in same round."""
        norm = NextTripBanNorm(key="ban", params={})
        context = _context(round_number=1)

        # First violation
        decision1 = NormDecision.violation(kept_kg=10.0, sanction="over_stock_limit")
        norm.on_agent_settled(context, "agent_0", decision1, harvested_kg=10.0)

        # Second violation (same agent, different reason)
        decision2 = NormDecision.violation(kept_kg=10.0, sanction="reserve_shortfall")
        norm.on_agent_settled(context, "agent_0", decision2, harvested_kg=10.0)

        state = context.norm_state("ban")
        assert state["agent_0"]["banned_next_round"] is True

    def test_non_qualifying_violation_does_not_ban(self):
        """Verify only specific sanctions trigger ban."""
        norm = NextTripBanNorm(key="ban", params={})
        context = _context(round_number=1)

        # Non-qualifying violation
        decision = NormDecision.violation(kept_kg=10.0, sanction="some_other_violation")
        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)

        state = context.norm_state("ban")
        assert "agent_0" not in state or not state.get("agent_0", {}).get("banned_next_round", False)


class TestExcessRedistributionEdgeCases:
    """Edge cases for excess_redistribution norm."""

    def test_no_compliant_agents(self):
        """Verify behavior when all agents violate."""
        norm = ExcessRedistributionNorm(key="redist", params={"stock_cap_key": "cap"})

        runtime = {
            "norms": {
                "cap": {
                    "violations": [
                        {"round": 1, "agent_id": "agent_0", "excess_kg": 10.0},
                        {"round": 1, "agent_id": "agent_1", "excess_kg": 5.0}
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
            "agent_1": {"participated": True, "harvested_kg": 15.0},
        }
        norm.on_round_end(context, round_results)

        # No compliant agents, so no redistribution
        state = context.norm_state("redist")
        assert "last_redistribution" in state
        assert state["last_redistribution"]["compliant_count"] == 0

    def test_agent_not_participating(self):
        """Verify non-participating agents don't receive redistribution."""
        norm = ExcessRedistributionNorm(key="redist", params={"stock_cap_key": "cap"})

        runtime = {
            "norms": {
                "cap": {
                    "violations": [{"round": 1, "agent_id": "agent_0", "excess_kg": 10.0}]
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
            "agent_1": {"participated": False, "harvested_kg": 0.0},  # Didn't participate
            "agent_2": {"participated": True, "harvested_kg": 5.0},   # Compliant
        }
        norm.on_round_end(context, round_results)

        # Only agent_2 should receive (didn't participate = not compliant)
        payoff = context.runtime["payoff"]
        assert payoff["agent_2"] == 10.0
        assert payoff["agent_1"] == 0.0

    def test_zero_excess(self):
        """Verify no redistribution when excess is zero."""
        norm = ExcessRedistributionNorm(key="redist", params={"stock_cap_key": "cap"})

        runtime = {
            "norms": {
                "cap": {
                    "violations": [{"round": 1, "agent_id": "agent_0", "excess_kg": 0.0}]
                }
            },
            "stock_kg": 300.0,
            "rounds": [],
            "payoff": {"agent_0": 0.0, "agent_1": 0.0}
        }
        context = _context(round_number=1, existing_runtime=runtime)

        round_results = {
            "agent_0": {"participated": True, "harvested_kg": 10.0},
            "agent_1": {"participated": True, "harvested_kg": 5.0},
        }
        norm.on_round_end(context, round_results)

        # No redistribution with zero excess
        state = context.norm_state("redist")
        assert "redistributions" not in state or len(state.get("redistributions", [])) == 0


class TestPolicyCompliance:
    """Tests verifying specific policy requirements from norm.txt."""

    def test_ten_percent_limit_enforced(self):
        """R2: Verify 10% limit is correctly calculated and enforced."""
        norm = PercentStockCapNorm(key="cap", params={"percent_limit": 0.10})

        # Stock of 200kg means 20kg limit
        runtime = {
            "norms": {"lake_watcher": {"current_estimate_kg": 200.0}},
            "stock_kg": 200.0,
            "rounds": [],
            "payoff": {}
        }
        context = _context(round_number=1, existing_runtime=runtime)

        decision = norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)

        # 10% of 200 = 20kg limit
        assert decision.kept_kg == 20.0
        assert decision.violated

    def test_one_kg_reserve_requirement(self):
        """R5: Verify 1kg reserve requirement is enforced."""
        norm = ReserveVerificationNorm(key="verify", params={"reserve_kg": 1.0})

        # Test with insufficient reserve
        runtime = {
            "norms": {"mandatory_reserve": {"agent_0": {"reserve_kg": 0.5}}},
            "stock_kg": 300.0,
            "rounds": [],
            "payoff": {}
        }
        context = _context(existing_runtime=runtime)

        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)

        assert decision.violated
        assert "1kg" in decision.note or "1 kg" in decision.note

    def test_ban_for_next_trip_only(self):
        """R8: Verify ban lasts exactly one trip."""
        norm = NextTripBanNorm(key="ban", params={})

        # Round 1: Violation
        context1 = _context(round_number=1)
        decision = NormDecision.violation(kept_kg=10.0, sanction="over_stock_limit")
        norm.on_agent_settled(context1, "agent_0", decision, harvested_kg=10.0)
        norm.on_round_end(context1, {})

        # Verify ban is active for round 2
        state1 = context1.norm_state("ban")
        assert state1["agent_0"]["banned_this_round"] is True

        # Round 2: Ban is served
        runtime = {
            "norms": {"ban": {"agent_0": {"banned_this_round": True, "banned_next_round": False}}},
            "stock_kg": 300.0,
            "rounds": [],
            "payoff": {}
        }
        context2 = _context(round_number=2, existing_runtime=runtime)

        # Agent is banned this round
        assert norm.is_eligible(context2, "agent_0") is False

        # End round 2
        norm.on_round_end(context2, {})

        # Ban should be cleared
        state2 = context2.norm_state("ban")
        assert state2["agent_0"]["banned_this_round"] is False
