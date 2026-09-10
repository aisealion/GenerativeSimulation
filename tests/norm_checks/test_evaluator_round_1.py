"""Independent evaluator tests for Round 1 norm implementation.

These tests verify the norm implementation against the specification
in state/norm_specs/round_1.md without trusting the implementer's tests.
"""

import pytest

from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from engine.norms.engine import NormEngine
from engine.norms import registry
from norms.catch_cap import CatchCapNorm
from norms.mandatory_reserve import MandatoryReserveNorm
from norms.violation_handler import ViolationHandlerNorm
from norms.repeated_violation_ban import RepeatedViolationBanNorm
from norms.monthly_stock_suspension import MonthlyStockSuspensionNorm


# Register norm types for testing
TEST_NORM_TYPES = {
    "catch_cap": CatchCapNorm,
    "mandatory_reserve": MandatoryReserveNorm,
    "violation_handler": ViolationHandlerNorm,
    "repeated_violation_ban": RepeatedViolationBanNorm,
    "monthly_stock_suspension": MonthlyStockSuspensionNorm,
}


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


class TestR1_CatchCap:
    """R1: Each fisher may take no more than 5 kg per trip."""

    def test_allows_under_limit(self):
        """R1: Catch below 5kg is allowed without violation."""
        norm = CatchCapNorm(key="cap", params={"limit_kg": 5.0})
        decision = norm.evaluate(_context(), "agent_0", raw_kg=4.5, proposed_kg=4.5)
        
        assert decision.kept_kg == 4.5
        assert not decision.violated
        assert decision.sanction is None

    def test_allows_exactly_at_limit(self):
        """R1: Catch exactly at 5kg is allowed without violation."""
        norm = CatchCapNorm(key="cap", params={"limit_kg": 5.0})
        decision = norm.evaluate(_context(), "agent_0", raw_kg=5.0, proposed_kg=5.0)
        
        assert decision.kept_kg == 5.0
        assert not decision.violated
        assert decision.sanction is None

    def test_trims_over_limit(self):
        """R1: Catch over 5kg is trimmed to 5kg."""
        norm = CatchCapNorm(key="cap", params={"limit_kg": 5.0})
        decision = norm.evaluate(_context(), "agent_0", raw_kg=8.0, proposed_kg=8.0)
        
        assert decision.kept_kg == 5.0

    def test_marks_over_limit_as_violation(self):
        """R1: Over-limit catch is marked as violation with sanction 'over_cap'."""
        norm = CatchCapNorm(key="cap", params={"limit_kg": 5.0})
        decision = norm.evaluate(_context(), "agent_0", raw_kg=8.0, proposed_kg=8.0)
        
        assert decision.violated
        assert decision.sanction == "over_cap"
        assert decision.note is not None

    def test_default_limit_is_5kg(self):
        """R1: Default limit is 5kg when not specified."""
        norm = CatchCapNorm(key="cap", params={})
        decision = norm.evaluate(_context(), "agent_0", raw_kg=6.0, proposed_kg=6.0)
        
        assert decision.kept_kg == 5.0
        assert decision.violated

    def test_provides_description(self):
        """R1: Catch cap provides description to agents."""
        norm = CatchCapNorm(key="cap", params={"limit_kg": 5.0})
        desc = norm.describe(_context(), "agent_0")
        
        assert desc is not None
        assert "5" in desc


class TestR2_MandatoryReserve:
    """R2: Each fisher must keep a mandatory 1 kg reserve."""

    def test_provides_description(self):
        """R2: Reserve norm provides description to agents."""
        norm = MandatoryReserveNorm(key="reserve", params={"reserve_kg": 1.0})
        desc = norm.describe(_context(), "agent_0")
        
        assert desc is not None
        assert "1" in desc or "reserve" in desc.lower()


class TestR3_LedgerRecording:
    """R3: The fisher records the catch on the communal ledger."""

    def test_ledger_tracks_agent_catch(self):
        """R3: Ledger tracks per-agent harvest information."""
        norm = MandatoryReserveNorm(key="reserve", params={"reserve_kg": 1.0})
        context = _context(round_number=3)
        decision = NormDecision.allow(kept_kg=4.0)
        
        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=4.0)
        
        state = context.norm_state("reserve")
        assert "ledger" in state
        assert len(state["ledger"]) == 1
        entry = state["ledger"][0]
        assert entry["agent_id"] == "agent_0"
        assert entry["round"] == 3
        assert entry["harvested_kg"] == 4.0


class TestR4_ViolationHandling:
    """R4: First offense - return 2kg to communal barrel and reminder."""

    def test_penalty_added_to_communal_barrel(self):
        """R4: 2kg penalty is added to communal barrel for violations."""
        norm = ViolationHandlerNorm(key="vh", params={"penalty_kg": 2.0})
        context = _context()
        decision = NormDecision.violation(kept_kg=5.0, sanction="over_cap")
        
        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=5.0)
        
        state = context.norm_state("vh")
        assert state["communal_barrel_kg"] == 2.0

    def test_violation_count_incremented(self):
        """R4: Violation count is incremented for first offense."""
        norm = ViolationHandlerNorm(key="vh", params={})
        context = _context()
        decision = NormDecision.violation(kept_kg=5.0, sanction="over_cap")
        
        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=5.0)
        
        state = context.norm_state("vh")
        assert state["violations"]["agent_0"]["count"] == 1

    def test_violation_recorded_in_ledger(self):
        """R4: Violation is recorded in the ledger."""
        norm = ViolationHandlerNorm(key="vh", params={})
        context = _context(round_number=5)
        decision = NormDecision.violation(kept_kg=5.0, sanction="over_cap")
        
        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=5.0)
        
        state = context.norm_state("vh")
        assert "ledger" in state
        ledger_entry = state["ledger"][0]
        assert ledger_entry["round"] == 5
        assert ledger_entry["agent_id"] == "agent_0"
        assert ledger_entry["transfer_kg"] == 2.0

    def test_penalty_for_under_reserve_violation(self):
        """R4: Penalty also applies to under_reserve violations."""
        norm = ViolationHandlerNorm(key="vh", params={})
        context = _context()
        decision = NormDecision.violation(kept_kg=0.5, sanction="under_reserve")
        
        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=0.5)
        
        state = context.norm_state("vh")
        assert state["violations"]["agent_0"]["count"] == 1
        assert state["communal_barrel_kg"] == 2.0


class TestR5_RepeatedViolationBan:
    """R5: Repeated violations (2nd+) result in one-week ban."""

    def test_eligible_with_no_violations(self):
        """R5: Agent with no violations is eligible."""
        norm = RepeatedViolationBanNorm(key="ban", params={})
        context = _context()
        
        assert norm.is_eligible(context, "agent_0") is True

    def test_ban_imposed_at_threshold(self):
        """R5: Ban is imposed when violation count reaches 2."""
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
        
        state = context.norm_state("ban")
        # ban_start = 6, ban_end = 6 + 7 - 1 = 12
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

    def test_eligible_after_ban_expires(self):
        """R5: Agent becomes eligible after ban expires."""
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

    def test_ban_duration_is_7_rounds(self):
        """R5: Ban duration is exactly 7 rounds."""
        norm = RepeatedViolationBanNorm(key="ban", params={
            "violation_threshold": 2,
            "ban_duration_rounds": 7
        })
        runtime = {
            "norms": {
                "violation_handler": {
                    "violations": {
                        "agent_0": {"count": 2, "history": []}
                    }
                }
            }
        }
        context = _context(round_number=5, existing_runtime=runtime)
        decision = NormDecision.allow(kept_kg=5.0)
        
        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=5.0)
        
        state = context.norm_state("ban")
        ban_end = state["agent_0"]["banned_until_round"]
        ban_start = state["agent_0"]["ban_start_round"]
        assert ban_end - ban_start + 1 == 7

    def test_ban_recorded_in_ledger(self):
        """R5: Ban is recorded in the ledger."""
        norm = RepeatedViolationBanNorm(key="ban", params={
            "violation_threshold": 2,
            "ban_duration_rounds": 7
        })
        runtime = {
            "norms": {
                "violation_handler": {
                    "violations": {
                        "agent_0": {"count": 2, "history": []}
                    }
                }
            }
        }
        context = _context(round_number=5, existing_runtime=runtime)
        decision = NormDecision.allow(kept_kg=5.0)
        
        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=5.0)
        
        state = context.norm_state("ban")
        assert "ledger" in state
        ledger_entry = state["ledger"][0]
        assert ledger_entry["action"] == "ban_imposed"
        assert ledger_entry["agent_id"] == "agent_0"


class TestR6_MonthlyStockMeasurement:
    """R6: Monthly stock measurements trigger suspension if below 200kg."""

    def test_measurement_occurs_at_interval(self):
        """R6: Measurement occurs every 30 rounds."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={
            "measurement_interval_rounds": 30
        })
        context = _context(stock_kg=250.0, round_number=30)
        
        norm.on_round_start(context)
        
        state = context.norm_state("suspension")
        assert state["last_measurement_round"] == 30

    def test_no_measurement_between_intervals(self):
        """R6: No measurement occurs between intervals."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={
            "measurement_interval_rounds": 30
        })
        context = _context(stock_kg=250.0, round_number=15)
        
        norm.on_round_start(context)
        
        state = context.norm_state("suspension")
        assert state.get("last_measurement_round", 0) != 15


class TestR7_CommunitySuspension:
    """R7: One-week suspension when stock < 200kg."""

    def test_suspension_triggered_below_threshold(self):
        """R7: Suspension is triggered when stock < 200kg."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={
            "threshold_kg": 200.0,
            "suspension_duration_rounds": 7
        })
        context = _context(stock_kg=150.0, round_number=30)
        
        norm.on_round_start(context)
        
        state = context.norm_state("suspension")
        # suspension_start = 31, suspension_end = 31 + 7 - 1 = 37
        assert state["suspension_end_round"] == 37

    def test_no_suspension_above_threshold(self):
        """R7: No suspension when stock >= 200kg."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={
            "threshold_kg": 200.0
        })
        context = _context(stock_kg=250.0, round_number=30)
        
        norm.on_round_start(context)
        
        state = context.norm_state("suspension")
        assert state.get("suspension_end_round", 0) <= 30

    def test_suspension_makes_all_ineligible(self):
        """R7: During suspension, all agents are ineligible."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={})
        runtime = {
            "norms": {
                "suspension": {
                    "suspension_end_round": 40
                }
            }
        }
        context = _context(round_number=35, existing_runtime=runtime)
        
        assert norm.is_eligible(context, "agent_0") is False
        assert norm.is_eligible(context, "agent_1") is False
        assert norm.is_eligible(context, "agent_2") is False

    def test_eligible_after_suspension_expires(self):
        """R7: Agents become eligible after suspension expires."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={})
        runtime = {
            "norms": {
                "suspension": {
                    "suspension_end_round": 40
                }
            }
        }
        context = _context(round_number=41, existing_runtime=runtime)
        
        assert norm.is_eligible(context, "agent_0") is True

    def test_suspension_duration_is_7_rounds(self):
        """R7: Suspension lasts exactly 7 rounds."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={
            "threshold_kg": 200.0,
            "suspension_duration_rounds": 7
        })
        context = _context(stock_kg=150.0, round_number=30)
        
        norm.on_round_start(context)
        
        state = context.norm_state("suspension")
        suspension_end = state["suspension_end_round"]
        # suspension_start = 31, suspension_end = 37, so 37 - 31 + 1 = 7
        assert suspension_end == 37

    def test_suspension_described_to_agents(self):
        """R7: Active suspension is described to agents."""
        norm = MonthlyStockSuspensionNorm(key="suspension", params={})
        runtime = {
            "norms": {
                "suspension": {
                    "suspension_end_round": 40,
                    "last_measurement_round": 30
                }
            }
        }
        context = _context(round_number=35, existing_runtime=runtime)
        
        desc = norm.describe(context, "agent_0")
        assert desc is not None
        assert "suspension" in desc.lower() or "suspended" in desc.lower()


class TestNormOrdering:
    """Tests that norms are applied in the correct order."""

    def test_catch_cap_before_mandatory_reserve(self, monkeypatch):
        """Config order: catch_cap should be before mandatory_reserve."""
        monkeypatch.setattr(registry, "NORM_TYPES", TEST_NORM_TYPES)
        
        config = {
            "norms": [
                {"type": "catch_cap", "limit_kg": 5.0},
                {"type": "mandatory_reserve", "reserve_kg": 1.0},
            ]
        }
        engine = NormEngine.from_config(config)
        
        assert len(engine.norms) == 2
        assert isinstance(engine.norms[0], CatchCapNorm)
        assert isinstance(engine.norms[1], MandatoryReserveNorm)


class TestIntegrationRequirements:
    """Integration tests for complete requirement satisfaction."""

    def test_violation_handler_reads_catch_cap_sanction(self, monkeypatch):
        """Integration: Violation handler responds to catch_cap's over_cap sanction."""
        monkeypatch.setattr(registry, "NORM_TYPES", TEST_NORM_TYPES)
        
        config = {
            "norms": [
                {"type": "catch_cap", "limit_kg": 5.0},
                {"type": "violation_handler", "penalty_kg": 2.0},
            ]
        }
        engine = NormEngine.from_config(config)
        context = _context(round_number=1)
        
        # Start round
        engine.start_round(context)
        
        # Apply to an agent with 8kg catch (should be trimmed to 5kg)
        final = engine.apply(context, "agent_0", raw_kg=8.0)
        
        # Verify final decision
        assert final.kept_kg == 5.0
        assert final.violated
        assert final.sanction == "over_cap"
        
        # Check violation was recorded
        state = context.norm_state("violation_handler")
        assert state["violations"]["agent_0"]["count"] == 1

    def test_ban_norm_reads_violation_handler_state(self, monkeypatch):
        """Integration: Ban norm reads violation count from violation_handler."""
        monkeypatch.setattr(registry, "NORM_TYPES", TEST_NORM_TYPES)
        
        # Pre-seed with 2 violations in violation_handler state
        runtime = {
            "stock_kg": 300.0,
            "rounds": [],
            "norms": {
                "violation_handler": {
                    "violations": {
                        "agent_0": {"count": 2, "history": [{}, {}]}
                    }
                }
            }
        }
        context = _context(round_number=5, existing_runtime=runtime)
        
        config = {
            "norms": [
                {"type": "repeated_violation_ban", "violation_threshold": 2, "ban_duration_rounds": 7},
            ]
        }
        engine = NormEngine.from_config(config)
        
        # Start round
        engine.start_round(context)
        
        # Apply (should trigger ban)
        final = engine.apply(context, "agent_0", raw_kg=5.0)
        
        # Verify ban was recorded
        state = context.norm_state("repeated_violation_ban")
        assert "agent_0" in state
        assert state["agent_0"]["banned_until_round"] == 12  # 5 + 1 + 7 - 1
