"""Tests for Round 2: Daily collective limit with proportional redistribution."""

import pytest
from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.daily_collective_limit import DailyCollectiveLimitNorm


class TestDailyCollectiveLimitIndividualCap:
    """Tests for the individual 15kg cap per trip."""

    def test_individual_cap_under_limit(self):
        """R2.1: Agent under cap keeps full amount."""
        norm = DailyCollectiveLimitNorm(key="test_limit", params={"individual_cap_kg": 15})
        context = HarvestContext(
            config={},
            fluents=[],
            runtime={},
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        # Agent catches 10 kg, under the 15 kg cap
        result = norm.evaluate(context, "agent_1", raw_kg=10.0, proposed_kg=10.0)

        assert result.kept_kg == 10.0
        assert not result.violated

    def test_individual_cap_at_limit(self):
        """R2.1: Agent at cap keeps exactly the limit."""
        norm = DailyCollectiveLimitNorm(key="test_limit", params={"individual_cap_kg": 15})
        context = HarvestContext(
            config={},
            fluents=[],
            runtime={},
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        # Agent catches 15 kg, exactly at cap
        result = norm.evaluate(context, "agent_1", raw_kg=15.0, proposed_kg=15.0)

        assert result.kept_kg == 15.0
        assert not result.violated

    def test_individual_cap_over_limit(self):
        """R2.1: Agent over cap is adjusted down to cap."""
        norm = DailyCollectiveLimitNorm(key="test_limit", params={"individual_cap_kg": 15})
        context = HarvestContext(
            config={},
            fluents=[],
            runtime={},
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        # Agent catches 25 kg, over the 15 kg cap
        result = norm.evaluate(context, "agent_1", raw_kg=25.0, proposed_kg=25.0)

        assert result.kept_kg == 15.0
        assert "cap" in result.note.lower()


class TestDailyCollectiveLimitSurplus:
    """Tests for collective limit and proportional redistribution."""

    def test_under_collective_limit_no_adjustment(self):
        """R2.2, R2.4: When total under 200kg, no surplus returned."""
        norm = DailyCollectiveLimitNorm(
            key="test_limit",
            params={"daily_limit_kg": 200, "individual_cap_kg": 15}
        )
        runtime = {}
        context = HarvestContext(
            config={},
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        # 5 agents at 15 kg each = 75 kg total (under 200 kg)
        for i in range(5):
            norm.evaluate(context, f"agent_{i}", raw_kg=20.0, proposed_kg=20.0)

        round_results = {
            f"agent_{i}": {"harvested_kg": 15.0, "effort": 0.5, "participated": True, "note": None}
            for i in range(5)
        }

        norm.on_round_end(context, round_results)

        # Verify pool is unchanged
        norm_state = context.norm_state("test_limit")
        assert norm_state.get("community_pool_kg", 0.0) == 0.0

        # Verify all agents keep their full amount
        for i in range(5):
            assert round_results[f"agent_{i}"]["harvested_kg"] == 15.0

    def test_over_collective_limit_proportional_reduction(self):
        """R2.5: Surplus divided proportionally when over limit."""
        norm = DailyCollectiveLimitNorm(
            key="test_limit",
            params={"daily_limit_kg": 200, "individual_cap_kg": 15}
        )
        runtime = {}
        context = HarvestContext(
            config={},
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        # 20 agents at 15 kg each = 300 kg total (100 kg over 200 kg limit)
        for i in range(20):
            norm.evaluate(context, f"agent_{i}", raw_kg=20.0, proposed_kg=20.0)

        round_results = {
            f"agent_{i}": {"harvested_kg": 15.0, "effort": 0.5, "participated": True, "note": None}
            for i in range(20)
        }

        norm.on_round_end(context, round_results)

        # Verify pool received the surplus
        norm_state = context.norm_state("test_limit")
        assert norm_state.get("community_pool_kg", 0.0) == 100.0

        # Each agent should have returned 5 kg (proportional share: 15/300 * 100 = 5)
        # So each keeps 10 kg
        for i in range(20):
            assert round_results[f"agent_{i}"]["harvested_kg"] == 10.0

    def test_proportional_calculation_varied_contributions(self):
        """R2.5: Agents contributing different amounts have different reductions."""
        norm = DailyCollectiveLimitNorm(
            key="test_limit",
            params={"daily_limit_kg": 100, "individual_cap_kg": 100}  # No individual cap for this test
        )
        runtime = {}
        context = HarvestContext(
            config={},
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        # Agent A: 60 kg, Agent B: 40 kg, Total: 100 kg, Limit: 100 kg
        # No surplus, no adjustment
        norm.evaluate(context, "agent_A", raw_kg=60.0, proposed_kg=60.0)
        norm.evaluate(context, "agent_B", raw_kg=40.0, proposed_kg=40.0)

        round_results = {
            "agent_A": {"harvested_kg": 60.0, "effort": 0.5, "participated": True, "note": None},
            "agent_B": {"harvested_kg": 40.0, "effort": 0.5, "participated": True, "note": None},
        }

        norm.on_round_end(context, round_results)

        # No surplus, amounts unchanged
        assert round_results["agent_A"]["harvested_kg"] == 60.0
        assert round_results["agent_B"]["harvested_kg"] == 40.0


class TestCommunityPoolTracking:
    """Tests for community pool cumulative tracking."""

    def test_pool_accumulates_across_rounds(self):
        """R2.6: Community pool cumulative across rounds."""
        norm = DailyCollectiveLimitNorm(
            key="test_limit",
            params={"daily_limit_kg": 100, "individual_cap_kg": 50}
        )

        # Round 1: 3 agents at 50 kg = 150 kg, surplus 50 kg
        runtime1 = {"norms": {"test_limit": {"community_pool_kg": 0.0}}}
        context1 = HarvestContext(
            config={},
            fluents=[],
            runtime=runtime1,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        for i in range(3):
            norm.evaluate(context1, f"agent_{i}", raw_kg=50.0, proposed_kg=50.0)

        round_results1 = {
            f"agent_{i}": {"harvested_kg": 50.0, "effort": 0.5, "participated": True, "note": None}
            for i in range(3)
        }

        norm.on_round_end(context1, round_results1)

        # Pool should have 50 kg from round 1 (allowing for floating point precision)
        assert abs(runtime1["norms"]["test_limit"]["community_pool_kg"] - 50.0) < 0.001

        # Round 2: Same scenario, should accumulate to 100 kg
        runtime2 = {"norms": {"test_limit": {"community_pool_kg": 50.0}}}
        context2 = HarvestContext(
            config={},
            fluents=[],
            runtime=runtime2,
            agents={},
            round_number=2,
            stock_before=1000.0,
        )

        for i in range(3):
            norm.evaluate(context2, f"agent_{i}", raw_kg=50.0, proposed_kg=50.0)

        round_results2 = {
            f"agent_{i}": {"harvested_kg": 50.0, "effort": 0.5, "participated": True, "note": None}
            for i in range(3)
        }

        norm.on_round_end(context2, round_results2)

        # Pool should now have 100 kg (50 + 50, allowing for floating point precision)
        assert abs(runtime2["norms"]["test_limit"]["community_pool_kg"] - 100.0) < 0.001


class TestDeficitTracking:
    """Tests for deficit tracking in edge cases."""

    def test_deficit_when_cannot_pay_full_share(self):
        """R2.7: Deficit accrued when agent's share exceeds their catch."""
        norm = DailyCollectiveLimitNorm(
            key="test_limit",
            params={"daily_limit_kg": 50, "individual_cap_kg": 100}  # High cap, low collective limit
        )
        runtime = {}
        context = HarvestContext(
            config={},
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        # Two agents: one big, one tiny
        # Agent A: 90 kg, Agent B: 10 kg, Total: 100 kg, Limit: 50 kg, Surplus: 50 kg
        # Agent A share: (90/100) * 50 = 45 kg, keeps 45 kg
        # Agent B share: (10/100) * 50 = 5 kg, keeps 5 kg (no deficit)
        norm.evaluate(context, "agent_A", raw_kg=90.0, proposed_kg=90.0)
        norm.evaluate(context, "agent_B", raw_kg=10.0, proposed_kg=10.0)

        round_results = {
            "agent_A": {"harvested_kg": 90.0, "effort": 0.5, "participated": True, "note": None},
            "agent_B": {"harvested_kg": 10.0, "effort": 0.5, "participated": True, "note": None},
        }

        norm.on_round_end(context, round_results)

        # Check results
        assert round_results["agent_A"]["harvested_kg"] == 45.0  # 90 - 45
        assert round_results["agent_B"]["harvested_kg"] == 5.0   # 10 - 5

        # Verify deficits (neither should have deficit in this case)
        norm_state = context.norm_state("test_limit")
        deficits = norm_state.get("agent_deficits", {})
        assert "agent_A" not in deficits
        assert "agent_B" not in deficits


class TestDescribe:
    """Tests for agent-facing descriptions."""

    def test_describe_includes_limits_and_pool(self):
        """R2.10: Description includes cap, limit, and pool total."""
        norm = DailyCollectiveLimitNorm(
            key="test_limit",
            params={"daily_limit_kg": 200, "individual_cap_kg": 15}
        )
        runtime = {"norms": {"test_limit": {"community_pool_kg": 50.0}}}
        context = HarvestContext(
            config={},
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        desc = norm.describe(context, "agent_1")

        assert "15 kg" in desc
        assert "200 kg" in desc
        assert "50.0 kg" in desc

    def test_describe_includes_deficit(self):
        """R2.10: Description includes deficit status when present."""
        norm = DailyCollectiveLimitNorm(
            key="test_limit",
            params={"daily_limit_kg": 200, "individual_cap_kg": 15}
        )
        runtime = {"norms": {"test_limit": {
            "community_pool_kg": 50.0,
            "agent_deficits": {"agent_1": 10.0}
        }}}
        context = HarvestContext(
            config={},
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        desc = norm.describe(context, "agent_1")

        assert "10.0 kg" in desc
        assert "owe" in desc.lower()
