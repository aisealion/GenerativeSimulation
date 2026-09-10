"""
Independent tests for Round 4 norm implementation: catch_limit_with_seasonal_reserve

Requirements to verify:
1. Fixed 6kg per-trip catch limit with forfeiture of excess
2. 90% collective stock rule (leave 10% untouched)
3. 10% deposit from every catch into shared reserve
4. Reserve must reach 12% of lake's final stock at season end
5. Proportional shortfall redistribution among fishers
6. Ban for limit violations or non-payment of obligations
"""

import pytest
from engine.norms.context import HarvestContext
from engine.norms.engine import NormEngine


def make_test_state(stock_kg=100.0, round_number=1, payoff=None, existing_norm_state=None):
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
            "agent_0": {"name": "Test Fisher"},
            "agent_1": {"name": "Test Fisher 2"},
            "agent_2": {"name": "Test Fisher 3"}
        },
        "round_number": round_number
    }
    return state


# ============================================================================
# Requirement 1: Fixed 6kg Per-Trip Catch Limit
# ============================================================================

class TestSixKgLimit:
    """Test that the 6kg per-trip limit is enforced."""

    def test_catch_at_6kg_allowed(self):
        """A catch of exactly 6kg should be allowed."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 6kg catch should be allowed
        decision = engine.apply(context, "agent_0", 6.0)

        assert decision.kept_kg == 5.4  # 6kg - 10% deposit = 5.4kg
        assert not decision.violated

    def test_catch_below_6kg_allowed(self):
        """A catch below 6kg should be allowed."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 5kg catch should be allowed
        decision = engine.apply(context, "agent_0", 5.0)

        assert decision.kept_kg == 4.5  # 5kg - 10% deposit = 4.5kg
        assert not decision.violated

    def test_catch_above_6kg_forfeits_excess(self):
        """A catch above 6kg should forfeit excess to reserve."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 8kg catch - only 6kg kept, 2kg forfeited
        decision = engine.apply(context, "agent_0", 8.0)

        assert decision.violated
        assert decision.kept_kg == 5.4  # 6kg - 10% deposit = 5.4kg

    def test_excess_added_to_reserve(self):
        """Excess over 6kg should be added to shared reserve."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 8kg catch - 6kg kept, 2kg excess + 0.6kg deposit = 2.6kg to reserve
        decision = engine.apply(context, "agent_0", 8.0)

        norm_state = context.norm_state("round_4_limit")
        # Reserve gets: 2kg (excess) + 0.6kg (10% of 6kg kept) = 2.6kg
        assert norm_state["shared_reserve"] == 2.6


# ============================================================================
# Requirement 2: 90% Collective Stock Rule
# ============================================================================

class TestNinetyPercentRule:
    """Test that the collective 90% rule is enforced."""

    def test_collective_cap_calculated_correctly(self):
        """Collective cap should be 90% of starting stock."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        scratch = context.round_scratch("round_4_limit")
        # 90% of 100kg = 90kg collective cap
        assert scratch["max_allowed_this_round"] == 90.0

    def test_cumulative_harvest_tracked(self):
        """Cumulative harvest should be tracked across agents."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # First agent takes 6kg
        decision1 = engine.apply(context, "agent_0", 6.0)
        scratch = context.round_scratch("round_4_limit")
        assert scratch["round_cumulative_harvest"] == 6.0

        # Second agent takes 5kg
        decision2 = engine.apply(context, "agent_1", 5.0)
        assert scratch["round_cumulative_harvest"] == 11.0

    def test_collective_cap_reduces_individual_limit(self):
        """If collective cap is nearly reached, individual limit is reduced."""
        state = make_test_state(stock_kg=20.0)  # 90% cap = 18kg
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # First agent takes 6kg (limited by 6kg rule, not collective cap)
        decision1 = engine.apply(context, "agent_0", 6.0)
        assert round(decision1.kept_kg, 1) == 5.4  # 6kg - 10% deposit

        # Second agent tries to take 6kg, plenty of collective remaining
        # (18kg cap - 6kg already taken = 12kg remaining)
        decision2 = engine.apply(context, "agent_1", 6.0)
        assert not decision2.violated
        assert round(decision2.kept_kg, 1) == 5.4  # 6kg - 10% deposit

    def test_collective_cap_blocks_fishing_when_reached(self):
        """When collective cap is reached, subsequent fishers are blocked."""
        state = make_test_state(stock_kg=8.0)  # 90% cap = 7.2kg
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # First agent takes 6kg (at 6kg individual limit)
        decision1 = engine.apply(context, "agent_0", 6.0)
        scratch = context.round_scratch("round_4_limit")
        # Cumulative tracks before deposit: 6kg
        assert scratch["round_cumulative_harvest"] == 6.0

        # Second agent takes 1.2kg (remaining collective cap)
        decision2 = engine.apply(context, "agent_1", 2.0)  # Tries 2kg, but only 1.2kg allowed
        # Should be violation since 2kg > 1.2kg remaining
        assert decision2.violated
        # Should get 1.2kg - 10% deposit = 1.08kg
        assert round(decision2.kept_kg, 2) == 1.08

        # Now cumulative = 7.2kg, which equals 90% cap
        assert scratch["round_cumulative_harvest"] == 7.2

        # Third agent should be ineligible (cap reached)
        norm = engine.norms[0]
        is_eligible = norm.is_eligible(context, "agent_2")
        assert not is_eligible


# ============================================================================
# Requirement 3: 10% Deposit Into Shared Reserve
# ============================================================================

class TestReserveDeposit:
    """Test that 10% of each catch is deposited into shared reserve."""

    def test_ten_percent_deposit_deducted(self):
        """10% of kept catch should be deducted as deposit."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 5kg catch
        decision = engine.apply(context, "agent_0", 5.0)

        # 10% of 5kg = 0.5kg to reserve, 4.5kg kept
        assert decision.kept_kg == 4.5

    def test_deposit_added_to_shared_reserve(self):
        """Deposit should be added to shared reserve."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 6kg catch, 0.6kg to reserve
        decision = engine.apply(context, "agent_0", 6.0)

        norm_state = context.norm_state("round_4_limit")
        assert round(norm_state["shared_reserve"], 1) == 0.6

    def test_season_deposits_tracked_per_agent(self):
        """Each agent's season deposits should be tracked."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 6kg catch
        decision = engine.apply(context, "agent_0", 6.0)

        norm_state = context.norm_state("round_4_limit")
        assert round(norm_state["season_deposits"]["agent_0"], 1) == 0.6

    def test_season_catches_tracked_per_agent(self):
        """Each agent's season catches should be tracked."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 6kg catch (before deposit)
        decision = engine.apply(context, "agent_0", 6.0)

        norm_state = context.norm_state("round_4_limit")
        # season_catches tracks before deposit: 6kg
        assert norm_state["season_catches"]["agent_0"] == 6.0


# ============================================================================
# Requirement 4 & 5: Season-End Reserve Target and Proportional Redistribution
# ============================================================================

class TestSeasonEndReserve:
    """Test season-end reserve target and proportional redistribution."""

    def test_reserve_target_calculated_at_round_end(self):
        """Required reserve should be 12% of final stock at round end."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Agent catches 6kg
        decision = engine.apply(context, "agent_0", 6.0)

        # Simulate end of round with 90kg final stock
        context.override_stock_after_regrowth(90.0)

        round_results = {
            "agent_0": {
                "effort": 1.0,
                "harvested_kg": decision.kept_kg,
                "participated": True,
                "note": decision.note
            }
        }

        # Required reserve = 12% of 90kg = 10.8kg
        # Actual reserve = 0.6kg (from 10% of 6kg)
        # Shortfall = 10.8kg - 0.6kg = 10.2kg
        engine.end_round(context, round_results)

        norm_state = context.norm_state("round_4_limit")
        # Proportional debt should be assigned
        assert "agent_0" in norm_state.get("proportional_debts", {})
        # agent_0 owes 100% of shortfall (only fisher)
        assert norm_state["proportional_debts"]["agent_0"] == 10.2

    def test_proportional_debt_split_among_multiple_agents(self):
        """Shortfall should be split proportionally among fishers."""
        state = make_test_state(stock_kg=100.0, payoff={"agent_0": 10.0, "agent_1": 10.0})
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # agent_0 catches 6kg
        decision0 = engine.apply(context, "agent_0", 6.0)
        # agent_1 catches 3kg
        decision1 = engine.apply(context, "agent_1", 3.0)

        # Final stock = 100 - 6 - 3 = 91kg
        # Required reserve = 12% of 91kg = 10.92kg
        # Actual reserve = 0.6 + 0.3 = 0.9kg
        # Shortfall = 10.92 - 0.9 = 10.02kg

        context.override_stock_after_regrowth(91.0)

        round_results = {
            "agent_0": {
                "effort": 1.0,
                "harvested_kg": decision0.kept_kg,
                "participated": True,
                "note": decision0.note
            },
            "agent_1": {
                "effort": 1.0,
                "harvested_kg": decision1.kept_kg,
                "participated": True,
                "note": decision1.note
            }
        }

        engine.end_round(context, round_results)

        norm_state = context.norm_state("round_4_limit")

        # agent_0 caught 6/9 = 2/3 of total, owes 2/3 of shortfall
        expected_debt_0 = 10.02 * (6.0 / 9.0)
        # agent_1 caught 3/9 = 1/3 of total, owes 1/3 of shortfall
        expected_debt_1 = 10.02 * (3.0 / 9.0)

        assert abs(norm_state["proportional_debts"]["agent_0"] - expected_debt_0) < 0.01
        assert abs(norm_state["proportional_debts"]["agent_1"] - expected_debt_1) < 0.01

    def test_season_tracking_reset_after_round_end(self):
        """Season catches and deposits should reset after round end."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        decision = engine.apply(context, "agent_0", 6.0)

        context.override_stock_after_regrowth(94.0)

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
        # Season tracking should be reset
        assert norm_state["season_catches"] == {}
        assert norm_state["season_deposits"] == {}

    def test_no_debt_if_reserve_target_met(self):
        """If reserve target is met, no proportional debt assigned."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Need to pre-populate reserve to meet target
        norm_state = context.norm_state("round_4_limit")
        norm_state["shared_reserve"] = 100.0  # Way above 12% of anything

        decision = engine.apply(context, "agent_0", 6.0)

        context.override_stock_after_regrowth(94.0)

        round_results = {
            "agent_0": {
                "effort": 1.0,
                "harvested_kg": decision.kept_kg,
                "participated": True,
                "note": decision.note
            }
        }

        engine.end_round(context, round_results)

        # No debt should be assigned since reserve > 12% of final stock
        assert "agent_0" not in norm_state.get("proportional_debts", {})


# ============================================================================
# Requirement 6: Ban for Violations and Non-Payment
# ============================================================================

class TestBanMechanism:
    """Test that violations result in bans."""

    def test_limit_violation_triggers_ban(self):
        """Exceeding the 6kg limit should trigger a ban."""
        state = make_test_state(stock_kg=100.0, round_number=5)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # Violation: 8kg catch
        decision = engine.apply(context, "agent_0", 8.0)

        assert decision.violated

        norm_state = context.norm_state("round_4_limit")
        assert "agent_0" in norm_state.get("ban_until", {})
        # Ban until after round 6 (current round 5 + 1 ban round + 1)
        assert norm_state["ban_until"]["agent_0"] == 7

    def test_banned_agent_is_ineligible(self):
        """A banned agent should be ineligible to fish during ban period."""
        existing_norm_state = {
            "round_4_limit": {
                "shared_reserve": 10.0,
                "ban_until": {"agent_0": 6}  # Banned until after round 5
            }
        }

        state = make_test_state(
            stock_kg=100.0,
            round_number=5,
            existing_norm_state=existing_norm_state
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])

        norm = engine.norms[0]
        is_eligible = norm.is_eligible(context, "agent_0")

        assert not is_eligible

    def test_ban_expires_after_period(self):
        """A ban should expire after the ban period."""
        existing_norm_state = {
            "round_4_limit": {
                "shared_reserve": 10.0,
                "ban_until": {"agent_0": 6}  # Banned until after round 5
            }
        }

        state = make_test_state(
            stock_kg=100.0,
            round_number=7,  # After ban period
            existing_norm_state=existing_norm_state
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])

        norm = engine.norms[0]
        is_eligible = norm.is_eligible(context, "agent_0")

        assert is_eligible

    def test_debt_deduction_from_next_catch(self):
        """Proportional debt should be deducted from next catch."""
        existing_norm_state = {
            "round_4_limit": {
                "shared_reserve": 10.0,
                "season_catches": {},
                "season_deposits": {},
                "proportional_debts": {"agent_0": 2.0}  # Owes 2kg
            }
        }

        state = make_test_state(
            stock_kg=100.0,
            round_number=2,
            existing_norm_state=existing_norm_state
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 6kg catch: 5.4kg after deposit, minus 2kg debt = 3.4kg
        decision = engine.apply(context, "agent_0", 6.0)

        assert round(decision.kept_kg, 1) == 3.4  # 6 - 0.6 (deposit) - 2.0 (debt)

        norm_state = context.norm_state("round_4_limit")
        # Debt should be cleared
        assert "agent_0" not in norm_state.get("proportional_debts", {})


# ============================================================================
# Transparency and Description Tests
# ============================================================================

class TestTransparency:
    """Test that describe() provides comprehensive information."""

    def test_describe_shows_6kg_limit(self):
        """Describe should show the 6kg per-trip limit."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        norm = engine.norms[0]
        description = norm.describe(context, "agent_0")

        assert "6.0kg" in description or "6kg" in description.lower()

    def test_describe_shows_collective_allowance(self):
        """Describe should show remaining collective allowance."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        norm = engine.norms[0]
        description = norm.describe(context, "agent_0")

        # 90% of 100kg = 90kg collective allowance
        assert "90.0kg" in description or "collective" in description.lower()

    def test_describe_shows_reserve_info(self):
        """Describe should show shared reserve balance."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        norm = engine.norms[0]
        description = norm.describe(context, "agent_0")

        assert "reserve" in description.lower()
        assert "10%" in description or "10 percent" in description.lower()

    def test_describe_shows_debt_info(self):
        """Describe should show proportional debt if owed."""
        existing_norm_state = {
            "round_4_limit": {
                "shared_reserve": 10.0,
                "proportional_debts": {"agent_0": 3.5}
            }
        }

        state = make_test_state(
            stock_kg=100.0,
            existing_norm_state=existing_norm_state
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        norm = engine.norms[0]
        description = norm.describe(context, "agent_0")

        assert "3.5kg" in description or "debt" in description.lower()
        assert "owe" in description.lower() or "deduct" in description.lower()


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exactly_6kg_no_violation(self):
        """Catch of exactly 6kg should not trigger violation."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        decision = engine.apply(context, "agent_0", 6.0)

        assert not decision.violated
        assert decision.kept_kg == 5.4  # After 10% deposit

    def test_just_over_6kg_triggers_violation(self):
        """Catch just over 6kg should trigger violation."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        decision = engine.apply(context, "agent_0", 6.1)

        assert decision.violated

    def test_zero_catch(self):
        """Zero catch should work without error."""
        state = make_test_state(stock_kg=100.0)
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        decision = engine.apply(context, "agent_0", 0.0)

        assert decision.kept_kg == 0.0
        assert not decision.violated

    def test_very_small_stock(self):
        """Very small stock should still enforce 90% rule correctly."""
        state = make_test_state(stock_kg=5.0)  # 90% cap = 4.5kg
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        decision = engine.apply(context, "agent_0", 6.0)

        # Effective limit = min(6kg, 4.5kg) = 4.5kg
        assert decision.violated
        assert decision.kept_kg == 4.05  # 4.5kg - 10% deposit

    def test_large_debt_exceeds_catch(self):
        """If debt exceeds available catch, agent gets nothing."""
        existing_norm_state = {
            "round_4_limit": {
                "shared_reserve": 10.0,
                "proportional_debts": {"agent_0": 10.0}  # Large debt
            }
        }

        state = make_test_state(
            stock_kg=100.0,
            existing_norm_state=existing_norm_state
        )
        context = HarvestContext.from_state(state)
        engine = NormEngine.from_config(state["config"])
        engine.start_round(context)

        # 6kg catch: 5.4kg after deposit, minus 5.4kg debt (can't take more than available)
        decision = engine.apply(context, "agent_0", 6.0)

        assert decision.kept_kg == 0.0  # All taken for debt

        norm_state = context.norm_state("round_4_limit")
        # Remaining debt should be recorded
        remaining_debt = 10.0 - 5.4  # Original - what was deducted
        assert norm_state["proportional_debts"]["agent_0"] == remaining_debt
