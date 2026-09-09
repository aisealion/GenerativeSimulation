"""
Tests for Round 1 norm: catch limit with forfeiture and bans.

Verifies:
- Catch limit enforced (min of 15% of stock or 20kg)
- Excess forfeited
- Bans issued for violations
- Banned fishers are ineligible
- Forfeited fish returned to stock
"""

import pytest
from engine.norms.context import HarvestContext
from engine.norms.engine import NormEngine


def make_test_state(stock_kg=100.0, round_number=1, existing_bans=None):
    """Create a minimal state for testing."""
    state = {
        "config": {
            "norms": [
                {
                    "type": "catch_limit_with_forfeiture",
                    "id": "test_limit",
                    "percent_limit": 0.15,
                    "kg_limit": 20.0,
                    "ban_days": 1
                }
            ]
        },
        "fluents": [],
        "runtime": {
            "stock_kg": stock_kg,
            "rounds": [],
            "payoff": {},
            "dead_agents": [],
            "norms": {}
        },
        "agents": {
            "agent_0": {"name": "Test Fisher"}
        },
        "round_number": round_number
    }

    # Set up existing bans if provided
    if existing_bans:
        state["runtime"]["norms"]["test_limit"] = {"bans": existing_bans}

    return state


class TestCatchLimitEnforcement:
    """Test that catch limits are properly enforced."""

    def test_catch_below_both_limits(self):
        """Catch below both 15% and 20kg should be allowed fully."""
        state = make_test_state(stock_kg=100.0)  # 15% = 15kg limit
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 10kg catch - below both limits
        decision = engine.apply(context, "agent_0", 10.0)

        assert decision.kept_kg == 10.0
        assert not decision.violated
        assert decision.sanction is None

    def test_catch_exceeds_percent_limit(self):
        """Catch exceeding 15% but under 20kg should cap at 15%."""
        state = make_test_state(stock_kg=100.0)  # 15% = 15kg, so limit is 15kg
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 18kg catch - exceeds 15% (15kg) but under 20kg
        decision = engine.apply(context, "agent_0", 18.0)

        assert decision.kept_kg == 15.0  # Capped at 15%
        assert decision.violated
        assert decision.sanction == "catch_limit_exceeded"
        assert "forfeited" in decision.note.lower()

    def test_catch_exceeds_kg_limit(self):
        """Catch exceeding 20kg but under 15% should cap at 20kg."""
        state = make_test_state(stock_kg=200.0)  # 15% = 30kg, so limit is 20kg
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 25kg catch - exceeds 20kg but under 15% (30kg)
        decision = engine.apply(context, "agent_0", 25.0)

        assert decision.kept_kg == 20.0  # Capped at 20kg
        assert decision.violated
        assert decision.sanction == "catch_limit_exceeded"

    def test_catch_exceeds_both_limits(self):
        """Catch exceeding both limits should cap at the lower one."""
        state = make_test_state(stock_kg=100.0)  # 15% = 15kg, so limit is 15kg
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 25kg catch - exceeds both 15% (15kg) and 20kg
        decision = engine.apply(context, "agent_0", 25.0)

        assert decision.kept_kg == 15.0  # Capped at 15% (the lower limit)
        assert decision.violated
        assert "15.0kg" in decision.note or "15kg" in decision.note


class TestBanMechanism:
    """Test that bans are properly issued and enforced."""

    def test_violation_issues_ban(self):
        """Exceeding limit should issue a one-day ban."""
        state = make_test_state(stock_kg=100.0, round_number=5)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Trigger violation
        decision = engine.apply(context, "agent_0", 25.0)

        assert decision.violated

        # Check ban was recorded in norm state
        norm_state = context.norm_state("test_limit")
        assert "bans" in norm_state
        assert "agent_0" in norm_state["bans"]
        # Ban until round 6 (current round 5 + 1)
        assert norm_state["bans"]["agent_0"] == 6

    def test_banned_fisher_ineligible(self):
        """Banned fisher should be ineligible to fish."""
        # Agent banned until round 6
        state = make_test_state(
            stock_kg=100.0,
            round_number=5,
            existing_bans={"agent_0": 6}
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Should be ineligible
        assert not engine.is_eligible(context, "agent_0")

    def test_expired_ban_allows_fishing(self):
        """Fisher with expired ban should be eligible."""
        # Agent banned until round 5, now it's round 6
        state = make_test_state(
            stock_kg=100.0,
            round_number=6,
            existing_bans={"agent_0": 5}
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Should be eligible (ban expired)
        assert engine.is_eligible(context, "agent_0")

    def test_ban_description(self):
        """Description should note ban status."""
        state = make_test_state(
            stock_kg=100.0,
            round_number=5,
            existing_bans={"agent_0": 7}  # Banned for 2 more rounds
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        description = engine.describe_constraints(context, "agent_0")
        assert "banned" in description.lower()
        assert "2" in description  # 2 more rounds


class TestForfeitureToStock:
    """Test that forfeited fish are returned to stock."""

    def test_forfeited_added_to_stock(self):
        """Forfeited fish should be added back to lake stock."""
        state = make_test_state(stock_kg=100.0, round_number=1)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Trigger forfeiture: 25kg catch, 15kg limit, 10kg forfeited
        decision = engine.apply(context, "agent_0", 25.0)

        # Forfeiture should be tracked
        scratch = context.round_scratch("test_limit")
        assert "agent_0" in scratch["forfeited_this_round"]
        assert scratch["forfeited_this_round"]["agent_0"] == 10.0

        # Simulate round end (normally harvest action would compute stock_after_regrowth)
        # We'll manually set up a scenario
        stock_after_regrowth = 80.0  # Simulated
        context.override_stock_after_regrowth(stock_after_regrowth)

        # Call on_round_end
        round_results = {
            "agent_0": {
                "effort": 1.0,
                "harvested_kg": decision.kept_kg,
                "participated": True,
                "note": decision.note
            }
        }
        engine.end_round(context, round_results)

        # Stock should be increased by forfeited amount
        expected_stock = stock_after_regrowth + 10.0
        assert context.stock_override_kg == expected_stock


class TestIntegration:
    """Integration tests combining multiple scenarios."""

    def test_full_violation_cycle(self):
        """Test complete cycle: violation → ban → ineligibility → expiry."""
        # Round 1: Agent violates limit
        state = make_test_state(stock_kg=100.0, round_number=1)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        decision = engine.apply(context, "agent_0", 25.0)
        assert decision.violated
        assert decision.kept_kg == 15.0

        # Check ban was recorded: ban_until = 2 (can fish again starting round 2)
        norm_state = context.norm_state("test_limit")
        assert norm_state["bans"]["agent_0"] == 2

        # Round 1 (same round): Agent should NOT be banned yet (ban applies from next round)
        # Actually, the ban is immediate - if ban_until > current_round, they're banned
        # Here ban_until = 2, current_round = 1, so 1 < 2 = True, banned
        assert not engine.is_eligible(context, "agent_0")

        # Round 2: Agent ban expired (ban_until = 2, current_round = 2, 2 < 2 = False, eligible)
        state2 = make_test_state(stock_kg=100.0, round_number=2)
        # Copy ban from previous round
        state2["runtime"]["norms"]["test_limit"] = {"bans": {"agent_0": 2}}
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        engine2.start_round(context2)

        # ban_until (2) <= current_round (2), so eligible
        assert engine2.is_eligible(context2, "agent_0")

    def test_describe_shows_limit_when_not_banned(self):
        """Description should show limit info for eligible fishers."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        description = engine.describe_constraints(context, "agent_0")
        assert "15%" in description or "15" in description
        assert "20" in description
        assert "limit" in description.lower()
