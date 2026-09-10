"""
Independent evaluator tests for Round 4 norm implementation.
These tests verify that the norm implementation matches the specification in state/norm_specs/round_4.md
"""

import pytest
from engine.norms.context import HarvestContext
from engine.norms.engine import NormEngine


def make_state(stock_kg=100.0, round_number=1, payoff=None, existing_norm_state=None):
    """Create a minimal state for testing Round 4 norm."""
    runtime = {
        "stock_kg": stock_kg,
        "rounds": [],
        "payoff": payoff or {},
        "dead_agents": [],
        "norms": existing_norm_state or {}
    }

    state = {
        "config": {
            "norms": [
                {
                    "type": "catch_limit_with_seasonal_reserve",
                    "id": "round_4_limit",
                    "max_kg_per_trip": 6.0,
                    "reserve_deposit_percent": 0.10,
                    "min_stock_percent_remaining": 0.10,
                    "season_end_reserve_percent": 0.12,
                    "ban_rounds": 1
                }
            ]
        },
        "fluents": [],
        "runtime": runtime,
        "agents": {
            "agent_0": {"name": "Fisher A"},
            "agent_1": {"name": "Fisher B"},
            "agent_2": {"name": "Fisher C"},
            "agent_3": {"name": "Fisher D"}
        },
        "round_number": round_number
    }
    return state


class TestRequirement1_SixKgLimit:
    """Requirement 1: Fixed 6kg per-trip catch limit with forfeiture of excess"""

    def test_exactly_6kg_is_allowed(self):
        """A catch of exactly 6kg should be allowed without violation."""
        state = make_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        decision = engine.apply(context, "agent_0", 6.0)

        assert not decision.violated, "Exactly 6kg should not be a violation"
        assert decision.kept_kg == 5.4, "Should keep 6kg minus 10% deposit = 5.4kg"

    def test_below_6kg_is_allowed(self):
        """A catch below 6kg should be allowed."""
        state = make_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        decision = engine.apply(context, "agent_0", 4.5)

        assert not decision.violated
        assert decision.kept_kg == 4.05  # 4.5 - 10%

    def test_excess_over_6kg_is_forfeited(self):
        """Excess over 6kg should be forfeited to reserve."""
        state = make_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        decision = engine.apply(context, "agent_0", 10.0)

        assert decision.violated, "10kg catch should trigger violation"
        assert decision.kept_kg == 5.4, "Should keep 6kg minus 10% deposit = 5.4kg"

        # Check reserve gets the excess
        norm_state = context.norm_state("round_4_limit")
        # Excess = 10 - 6 = 4kg, plus 10% deposit of 6kg = 0.6kg, total = 4.6kg
        assert norm_state["shared_reserve"] == 4.6, "Reserve should get excess + deposit"

    def test_violation_records_ban(self):
        """A violation should result in a ban for the next round."""
        state = make_state(stock_kg=100.0, round_number=3)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        decision = engine.apply(context, "agent_0", 8.0)

        assert decision.violated
        norm_state = context.norm_state("round_4_limit")
        assert "agent_0" in norm_state["ban_until"]
        # Current round 3 + 1 ban round + 1 = 5 (ban_until is exclusive)
        assert norm_state["ban_until"]["agent_0"] == 5


class TestRequirement2_NinetyPercentRule:
    """Requirement 2: 90% collective stock rule (leave 10% untouched)"""

    def test_collective_cap_is_90_percent(self):
        """Collective cap should be 90% of starting stock."""
        state = make_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        scratch = context.round_scratch("round_4_limit")
        assert scratch["max_allowed_this_round"] == 90.0, "90% of 100kg = 90kg"

    def test_collective_cap_tracked_across_agents(self):
        """Cumulative harvest should track across all agents."""
        state = make_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Agent 0 takes 6kg
        engine.apply(context, "agent_0", 6.0)
        scratch = context.round_scratch("round_4_limit")
        assert scratch["round_cumulative_harvest"] == 6.0

        # Agent 1 takes 6kg
        engine.apply(context, "agent_1", 6.0)
        assert scratch["round_cumulative_harvest"] == 12.0

    def test_effective_limit_is_min_of_6kg_and_collective_remaining(self):
        """Effective limit should be min(6kg, remaining_collective)."""
        state = make_state(stock_kg=10.0)  # 90% cap = 9kg
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # First agent takes 6kg (limited by 6kg individual cap, not collective)
        decision1 = engine.apply(context, "agent_0", 6.0)
        assert not decision1.violated  # 6kg <= 9kg collective remaining

        # Second agent tries to take 6kg, but only 3kg collective remaining
        decision2 = engine.apply(context, "agent_1", 6.0)
        assert decision2.violated, "Should violate due to collective cap"
        # Effective limit = 3kg, after 10% deposit = 2.7kg
        assert decision2.kept_kg == 2.7

    def test_ineligible_when_collective_cap_reached(self):
        """Agents should be ineligible when collective cap is reached."""
        state = make_state(stock_kg=10.0)  # 90% cap = 9kg
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # First two agents take everything
        engine.apply(context, "agent_0", 6.0)
        engine.apply(context, "agent_1", 3.0)  # Only 3kg remaining

        # Third agent should be ineligible
        norm = engine.norms[0]
        assert not norm.is_eligible(context, "agent_2")


class TestRequirement3_ReserveDeposit:
    """Requirement 3: 10% deposit from every catch into shared reserve"""

    def test_ten_percent_deposit_from_allowed_catch(self):
        """10% of kept catch should go to reserve."""
        state = make_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        decision = engine.apply(context, "agent_0", 5.0)

        # 5kg catch, 10% = 0.5kg to reserve, 4.5kg kept
        assert decision.kept_kg == 4.5
        norm_state = context.norm_state("round_4_limit")
        assert norm_state["shared_reserve"] == 0.5

    def test_ten_percent_deposit_from_limited_catch(self):
        """10% deposit calculated from limited amount, not raw catch."""
        state = make_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        decision = engine.apply(context, "agent_0", 8.0)  # Limited to 6kg

        # 6kg limited, 10% = 0.6kg to reserve, plus 2kg excess = 2.6kg total
        norm_state = context.norm_state("round_4_limit")
        assert norm_state["shared_reserve"] == 2.6

    def test_deposit_tracked_per_agent(self):
        """Each agent's deposits should be tracked separately."""
        state = make_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        engine.apply(context, "agent_0", 6.0)  # 0.6kg deposit
        engine.apply(context, "agent_1", 4.0)  # 0.4kg deposit

        norm_state = context.norm_state("round_4_limit")
        assert abs(norm_state["season_deposits"]["agent_0"] - 0.6) < 0.001
        assert abs(norm_state["season_deposits"]["agent_1"] - 0.4) < 0.001

    def test_catch_tracked_before_deposit(self):
        """Season catches should track amount before deposit."""
        state = make_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        engine.apply(context, "agent_0", 6.0)

        norm_state = context.norm_state("round_4_limit")
        assert norm_state["season_catches"]["agent_0"] == 6.0  # Before 10% deposit


class TestRequirement4_SeasonEndReserve:
    """Requirement 4: Reserve must reach 12% of lake's final stock at season end"""

    def test_reserve_target_calculated_correctly(self):
        """Required reserve should be 12% of final stock."""
        state = make_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Agent catches 6kg, contributes 0.6kg to reserve
        decision = engine.apply(context, "agent_0", 6.0)

        # Final stock = 94kg (100 - 6)
        context.override_stock_after_regrowth(94.0)

        # Required reserve = 12% of 94kg = 11.28kg
        # Actual reserve = 0.6kg
        # Shortfall = 10.68kg

        round_results = {
            "agent_0": {
                "effort": 1.0,
                "harvested_kg": decision.kept_kg,
                "participated": True,
                "note": decision.note
            }
        }

        engine.end_round(context, round_results)

        norm_state = context.norm_state("round_4_limit")
        assert "agent_0" in norm_state.get("proportional_debts", {})
        # 10.68kg shortfall, agent_0 caught all, owes all
        assert abs(norm_state["proportional_debts"]["agent_0"] - 10.68) < 0.01


class TestRequirement5_ProportionalRedistribution:
    """Requirement 5: Proportional shortfall redistribution among fishers"""

    def test_shortfall_split_proportionally(self):
        """Shortfall should be split based on each fisher's catch proportion."""
        state = make_state(stock_kg=100.0, payoff={"agent_0": 10, "agent_1": 10, "agent_2": 10})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # agent_0: 6kg catch
        d0 = engine.apply(context, "agent_0", 6.0)
        # agent_1: 3kg catch
        d1 = engine.apply(context, "agent_1", 3.0)
        # agent_2: 0kg (no catch)

        # Total catch = 9kg, deposits = 0.9kg
        # Final stock = 91kg
        # Required = 12% of 91 = 10.92kg
        # Shortfall = 10.92 - 0.9 = 10.02kg

        context.override_stock_after_regrowth(91.0)

        round_results = {
            "agent_0": {"effort": 1.0, "harvested_kg": d0.kept_kg, "participated": True, "note": d0.note},
            "agent_1": {"effort": 1.0, "harvested_kg": d1.kept_kg, "participated": True, "note": d1.note}
        }

        engine.end_round(context, round_results)

        norm_state = context.norm_state("round_4_limit")

        # agent_0 caught 6/9 = 2/3
        expected_0 = 10.02 * (6.0 / 9.0)
        # agent_1 caught 3/9 = 1/3
        expected_1 = 10.02 * (3.0 / 9.0)

        assert abs(norm_state["proportional_debts"]["agent_0"] - expected_0) < 0.01
        assert abs(norm_state["proportional_debts"]["agent_1"] - expected_1) < 0.01

    def test_only_fishers_with_catches_get_debt(self):
        """Only agents who caught fish should get proportional debt."""
        state = make_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Only agent_0 catches
        d0 = engine.apply(context, "agent_0", 6.0)

        context.override_stock_after_regrowth(94.0)

        round_results = {
            "agent_0": {"effort": 1.0, "harvested_kg": d0.kept_kg, "participated": True, "note": d0.note}
        }

        engine.end_round(context, round_results)

        norm_state = context.norm_state("round_4_limit")

        assert "agent_0" in norm_state.get("proportional_debts", {})
        assert "agent_1" not in norm_state.get("proportional_debts", {})
        assert "agent_2" not in norm_state.get("proportional_debts", {})


class TestRequirement6_BanMechanism:
    """Requirement 6: Ban for limit violations or non-payment of obligations"""

    def test_ban_makes_agent_ineligible(self):
        """Banned agent should not be eligible to fish."""
        existing_norm_state = {
            "round_4_limit": {
                "shared_reserve": 10.0,
                "ban_until": {"agent_0": 5}  # Banned until after round 4
            }
        }

        state = make_state(stock_kg=100.0, round_number=4, existing_norm_state=existing_norm_state)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])

        norm = engine.norms[0]
        assert not norm.is_eligible(context, "agent_0")

    def test_ban_expires_after_round(self):
        """Ban should expire after the ban period."""
        existing_norm_state = {
            "round_4_limit": {
                "shared_reserve": 10.0,
                "ban_until": {"agent_0": 5}  # Banned until after round 4
            }
        }

        state = make_state(stock_kg=100.0, round_number=5, existing_norm_state=existing_norm_state)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])

        norm = engine.norms[0]
        assert norm.is_eligible(context, "agent_0")

    def test_violation_triggers_ban_next_round(self):
        """A violation should ban the agent for the next round."""
        state = make_state(stock_kg=100.0, round_number=1)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        engine.apply(context, "agent_0", 8.0)  # Violation

        norm_state = context.norm_state("round_4_limit")
        # ban_until should be current round (1) + 1 ban round + 1 = 3
        assert norm_state["ban_until"]["agent_0"] == 3

    def test_proportional_debt_deducted_from_next_catch(self):
        """Debt from previous season should be deducted from next catch."""
        existing_norm_state = {
            "round_4_limit": {
                "shared_reserve": 10.0,
                "season_catches": {},
                "season_deposits": {},
                "proportional_debts": {"agent_0": 3.0}
            }
        }

        state = make_state(stock_kg=100.0, round_number=2, existing_norm_state=existing_norm_state)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 6kg catch: 5.4kg after deposit, minus 3kg debt = 2.4kg
        decision = engine.apply(context, "agent_0", 6.0)

        assert abs(decision.kept_kg - 2.4) < 0.001

        norm_state = context.norm_state("round_4_limit")
        # Debt should be cleared
        assert "agent_0" not in norm_state.get("proportional_debts", {})

    def test_partial_debt_deduction(self):
        """If catch is smaller than debt, deduct what is available."""
        existing_norm_state = {
            "round_4_limit": {
                "shared_reserve": 10.0,
                "season_catches": {},
                "season_deposits": {},
                "proportional_debts": {"agent_0": 10.0}  # Large debt
            }
        }

        state = make_state(stock_kg=100.0, round_number=2, existing_norm_state=existing_norm_state)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 6kg catch: 5.4kg after deposit, all taken for debt
        decision = engine.apply(context, "agent_0", 6.0)

        assert decision.kept_kg == 0.0

        norm_state = context.norm_state("round_4_limit")
        # Remaining debt = 10 - 5.4 = 4.6
        assert abs(norm_state["proportional_debts"]["agent_0"] - 4.6) < 0.01


class TestConfigReplacement:
    """Test that Round 3 norm was replaced by Round 4 norm."""

    def test_round_3_norm_not_in_config(self):
        """Round 3 tiered norm should not be in config."""
        import json
        import os

        config_path = os.path.join(os.path.dirname(__file__), "../../state/config.json")
        with open(config_path) as f:
            config = json.load(f)

        norm_types = [n["type"] for n in config.get("norms", [])]
        assert "tiered_catch_limit_with_forfeiture" not in norm_types, \
            "Round 3 norm should be replaced, not present"

    def test_round_4_norm_in_config(self):
        """Round 4 norm should be in config."""
        import json
        import os

        config_path = os.path.join(os.path.dirname(__file__), "../../state/config.json")
        with open(config_path) as f:
            config = json.load(f)

        norm_types = [n["type"] for n in config.get("norms", [])]
        assert "catch_limit_with_seasonal_reserve" in norm_types, \
            "Round 4 norm should be present"

    def test_config_has_correct_parameters(self):
        """Config should have correct parameters for Round 4 norm."""
        import json
        import os

        config_path = os.path.join(os.path.dirname(__file__), "../../state/config.json")
        with open(config_path) as f:
            config = json.load(f)

        round_4_norm = None
        for n in config.get("norms", []):
            if n["type"] == "catch_limit_with_seasonal_reserve":
                round_4_norm = n
                break

        assert round_4_norm is not None
        assert round_4_norm["max_kg_per_trip"] == 6.0
        assert round_4_norm["reserve_deposit_percent"] == 0.10
        assert round_4_norm["min_stock_percent_remaining"] == 0.10
        assert round_4_norm["season_end_reserve_percent"] == 0.12
        assert round_4_norm["ban_rounds"] == 1


class TestRoundStateReset:
    """Test that round-specific state is reset each round."""

    def test_cumulative_harvest_reset_each_round(self):
        """Cumulative harvest should reset at start of each round."""
        # First round
        state1 = make_state(stock_kg=100.0, round_number=1)
        context1 = HarvestContext.from_state(state1)
        engine1 = NormEngine.from_config(state1["config"])
        engine1.start_round(context1)

        engine1.apply(context1, "agent_0", 6.0)
        scratch1 = context1.round_scratch("round_4_limit")
        assert scratch1["round_cumulative_harvest"] == 6.0

        # Second round - new context and engine
        state2 = make_state(stock_kg=94.0, round_number=2)
        context2 = HarvestContext.from_state(state2)
        engine2 = NormEngine.from_config(state2["config"])
        engine2.start_round(context2)

        scratch2 = context2.round_scratch("round_4_limit")
        assert scratch2["round_cumulative_harvest"] == 0.0, \
            "Cumulative harvest should reset for new round"

    def test_season_tracking_reset_after_season_end(self):
        """Season catches and deposits should reset after round end."""
        state = make_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        engine.apply(context, "agent_0", 6.0)

        norm_state = context.norm_state("round_4_limit")
        assert norm_state["season_catches"]["agent_0"] == 6.0

        context.override_stock_after_regrowth(94.0)

        round_results = {
            "agent_0": {
                "effort": 1.0,
                "harvested_kg": 5.4,
                "participated": True,
                "note": ""
            }
        }

        engine.end_round(context, round_results)

        assert norm_state["season_catches"] == {}
        assert norm_state["season_deposits"] == {}


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_catch(self):
        """Zero catch should work without error."""
        state = make_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        decision = engine.apply(context, "agent_0", 0.0)

        assert decision.kept_kg == 0.0
        assert not decision.violated

    def test_very_small_stock_90_percent(self):
        """With very small stock, 90% rule should still apply."""
        state = make_state(stock_kg=5.0)  # 90% = 4.5kg
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Agent tries 6kg, but collective cap is 4.5kg
        decision = engine.apply(context, "agent_0", 6.0)

        assert decision.violated
        # Effective limit = 4.5kg, after 10% deposit = 4.05kg
        assert decision.kept_kg == 4.05

    def test_multiple_agents_exceed_collective_cap(self):
        """Multiple agents hitting collective cap."""
        state = make_state(stock_kg=20.0)  # 90% = 18kg
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Three agents take 6kg each = 18kg exactly
        d0 = engine.apply(context, "agent_0", 6.0)
        d1 = engine.apply(context, "agent_1", 6.0)
        d2 = engine.apply(context, "agent_2", 6.0)

        assert not d0.violated
        assert not d1.violated
        assert not d2.violated

        # Fourth agent should be ineligible
        norm = engine.norms[0]
        assert not norm.is_eligible(context, "agent_3")

    def test_debt_paid_adds_to_reserve(self):
        """When debt is paid from catch, it should add to reserve."""
        existing_norm_state = {
            "round_4_limit": {
                "shared_reserve": 10.0,
                "season_catches": {},
                "season_deposits": {},
                "proportional_debts": {"agent_0": 2.0}
            }
        }

        state = make_state(stock_kg=100.0, round_number=2, existing_norm_state=existing_norm_state)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        initial_reserve = 10.0
        engine.apply(context, "agent_0", 6.0)

        norm_state = context.norm_state("round_4_limit")
        # Reserve gets: 0.6kg (10% deposit) + 2.0kg (debt payment) = 2.6kg more
        assert abs(norm_state["shared_reserve"] - (initial_reserve + 2.6)) < 0.01

    def test_reserve_persists_across_rounds(self):
        """Shared reserve should persist across rounds."""
        existing_norm_state = {
            "round_4_limit": {
                "shared_reserve": 15.0,
                "season_catches": {},
                "season_deposits": {}
            }
        }

        state = make_state(stock_kg=100.0, round_number=2, existing_norm_state=existing_norm_state)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        engine.apply(context, "agent_0", 6.0)  # Adds 0.6kg to reserve

        norm_state = context.norm_state("round_4_limit")
        assert abs(norm_state["shared_reserve"] - 15.6) < 0.01
