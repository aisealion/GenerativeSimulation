"""Tests for Round 2: Deficit penalty (10% forfeiture)."""

import pytest
from engine.norms.context import HarvestContext
from norms.deficit_penalty import DeficitPenaltyNorm


class TestDeficitPenaltyApplication:
    """Tests for penalty application when deficit exists."""

    def test_no_penalty_without_deficit(self):
        """R2.8: No penalty when agent has no deficit."""
        norm = DeficitPenaltyNorm(key="test_penalty", params={"penalty_rate": 0.10})
        runtime = {"norms": {"daily_collective_limit": {"agent_deficits": {}}}}
        context = HarvestContext(
            config={"norms": [{"type": "daily_collective_limit", "id": "daily_collective_limit"}]},
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        result = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)

        assert result.kept_kg == 20.0
        assert not result.violated

    def test_penalty_applied_with_deficit(self):
        """R2.8: 10% penalty applied when agent has deficit."""
        norm = DeficitPenaltyNorm(key="test_penalty", params={"penalty_rate": 0.10})
        runtime = {"norms": {"daily_collective_limit": {
            "agent_deficits": {"agent_1": 5.0},
            "community_pool_kg": 100.0,
        }}}
        context = HarvestContext(
            config={"norms": [{"type": "daily_collective_limit", "id": "daily_collective_limit"}]},
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        # Agent catches 20 kg, should forfeit 10% = 2 kg
        result = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)

        assert result.kept_kg == 18.0  # 20 - 2
        assert "forfeit" in result.note.lower() or "penalty" in result.note.lower()

    def test_penalty_reduces_deficit(self):
        """R2.8: Penalty amount reduces the deficit."""
        norm = DeficitPenaltyNorm(key="test_penalty", params={"penalty_rate": 0.10})
        runtime = {"norms": {"daily_collective_limit": {
            "agent_deficits": {"agent_1": 5.0},
            "community_pool_kg": 100.0,
        }}}
        context = HarvestContext(
            config={"norms": [{"type": "daily_collective_limit", "id": "daily_collective_limit"}]},
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        # Agent catches 20 kg, forfeit 2 kg, deficit should reduce from 5 to 3
        norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)

        deficits = runtime["norms"]["daily_collective_limit"]["agent_deficits"]
        assert deficits["agent_1"] == 3.0  # 5 - 2

    def test_penalty_adds_to_community_pool(self):
        """R2.8: Forfeited amount added to community pool."""
        norm = DeficitPenaltyNorm(key="test_penalty", params={"penalty_rate": 0.10})
        runtime = {"norms": {"daily_collective_limit": {
            "agent_deficits": {"agent_1": 5.0},
            "community_pool_kg": 100.0,
        }}}
        context = HarvestContext(
            config={"norms": [{"type": "daily_collective_limit", "id": "daily_collective_limit"}]},
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        # Agent catches 20 kg, forfeit 2 kg, pool should increase from 100 to 102
        norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)

        pool = runtime["norms"]["daily_collective_limit"]["community_pool_kg"]
        assert pool == 102.0  # 100 + 2


class TestDeficitClearing:
    """Tests for deficit being cleared over multiple rounds."""

    def test_deficit_fully_cleared(self):
        """R2.9: Deficit cleared when penalty exceeds remaining deficit."""
        norm = DeficitPenaltyNorm(key="test_penalty", params={"penalty_rate": 0.10})
        runtime = {"norms": {"daily_collective_limit": {
            "agent_deficits": {"agent_1": 1.0},  # Small deficit
            "community_pool_kg": 100.0,
        }}}
        context = HarvestContext(
            config={"norms": [{"type": "daily_collective_limit", "id": "daily_collective_limit"}]},
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        # Agent catches 20 kg, 10% = 2 kg penalty, but deficit is only 1 kg
        # Should only forfeit 1 kg, deficit cleared
        result = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)

        assert result.kept_kg == 19.0  # 20 - 1 (not 2)

        deficits = runtime["norms"]["daily_collective_limit"]["agent_deficits"]
        assert "agent_1" not in deficits  # Deficit cleared

    def test_deficit_cleared_message(self):
        """R2.9: Appropriate message when deficit is cleared."""
        norm = DeficitPenaltyNorm(key="test_penalty", params={"penalty_rate": 0.10})
        runtime = {"norms": {"daily_collective_limit": {
            "agent_deficits": {"agent_1": 1.0},
            "community_pool_kg": 100.0,
        }}}
        context = HarvestContext(
            config={"norms": [{"type": "daily_collective_limit", "id": "daily_collective_limit"}]},
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        result = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)

        assert "clear" in result.note.lower()

    def test_deficit_partially_cleared(self):
        """R2.9: Deficit reduced but not cleared when penalty is smaller."""
        norm = DeficitPenaltyNorm(key="test_penalty", params={"penalty_rate": 0.10})
        runtime = {"norms": {"daily_collective_limit": {
            "agent_deficits": {"agent_1": 10.0},  # Large deficit
            "community_pool_kg": 100.0,
        }}}
        context = HarvestContext(
            config={"norms": [{"type": "daily_collective_limit", "id": "daily_collective_limit"}]},
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        # Agent catches 20 kg, 10% = 2 kg penalty, deficit goes from 10 to 8
        result = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)

        assert result.kept_kg == 18.0  # 20 - 2

        deficits = runtime["norms"]["daily_collective_limit"]["agent_deficits"]
        assert deficits["agent_1"] == 8.0  # 10 - 2


class TestPenaltyOverMultipleRounds:
    """Tests for penalty persisting across rounds until deficit cleared."""

    def test_penalty_persists_across_rounds(self):
        """R2.9: Penalty continues each round until deficit is zero."""
        norm = DeficitPenaltyNorm(key="test_penalty", params={"penalty_rate": 0.10})

        # Round 1: Deficit of 5 kg
        runtime1 = {"norms": {"daily_collective_limit": {
            "agent_deficits": {"agent_1": 5.0},
            "community_pool_kg": 0.0,
        }}}
        context1 = HarvestContext(
            config={"norms": [{"type": "daily_collective_limit", "id": "daily_collective_limit"}]},
            fluents=[],
            runtime=runtime1,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        # Catch 20 kg, forfeit 2 kg, deficit reduces to 3 kg
        norm.evaluate(context1, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        assert runtime1["norms"]["daily_collective_limit"]["agent_deficits"]["agent_1"] == 3.0

        # Round 2: Still has deficit of 3 kg
        runtime2 = {"norms": {"daily_collective_limit": {
            "agent_deficits": {"agent_1": 3.0},
            "community_pool_kg": 2.0,
        }}}
        context2 = HarvestContext(
            config={"norms": [{"type": "daily_collective_limit", "id": "daily_collective_limit"}]},
            fluents=[],
            runtime=runtime2,
            agents={},
            round_number=2,
            stock_before=1000.0,
        )

        # Catch 20 kg again, forfeit another 2 kg, deficit reduces to 1 kg
        norm.evaluate(context2, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        assert runtime2["norms"]["daily_collective_limit"]["agent_deficits"]["agent_1"] == 1.0

        # Round 3: Deficit of 1 kg
        runtime3 = {"norms": {"daily_collective_limit": {
            "agent_deficits": {"agent_1": 1.0},
            "community_pool_kg": 4.0,
        }}}
        context3 = HarvestContext(
            config={"norms": [{"type": "daily_collective_limit", "id": "daily_collective_limit"}]},
            fluents=[],
            runtime=runtime3,
            agents={},
            round_number=3,
            stock_before=1000.0,
        )

        # Catch 20 kg, forfeit 1 kg (clears deficit), kept 19 kg
        result = norm.evaluate(context3, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        assert result.kept_kg == 19.0
        assert "agent_1" not in runtime3["norms"]["daily_collective_limit"]["agent_deficits"]


class TestDescribe:
    """Tests for agent-facing descriptions."""

    def test_describe_none_when_no_deficit(self):
        """R2.10: No description when agent has no deficit."""
        norm = DeficitPenaltyNorm(key="test_penalty", params={"penalty_rate": 0.10})
        runtime = {"norms": {"daily_collective_limit": {"agent_deficits": {}}}}
        context = HarvestContext(
            config={"norms": [{"type": "daily_collective_limit", "id": "daily_collective_limit"}]},
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        desc = norm.describe(context, "agent_1")

        assert desc is None

    def test_describe_shows_deficit(self):
        """R2.10: Description shows deficit amount and penalty warning."""
        norm = DeficitPenaltyNorm(key="test_penalty", params={"penalty_rate": 0.10})
        runtime = {"norms": {"daily_collective_limit": {
            "agent_deficits": {"agent_1": 7.5},
            "community_pool_kg": 100.0,
        }}}
        context = HarvestContext(
            config={"norms": [{"type": "daily_collective_limit", "id": "daily_collective_limit"}]},
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=1,
            stock_before=1000.0,
        )

        desc = norm.describe(context, "agent_1")

        assert "7.5" in desc or "7.5 kg" in desc
        assert "deficit" in desc.lower()
        assert "10%" in desc
