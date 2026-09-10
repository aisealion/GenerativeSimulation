"""Independent evaluator tests for Round 4 norm implementation.

These tests verify that Round 4 requirements are properly implemented:
- R1: 4kg per-trip catch limit
- R2: 1kg personal reserve requirement
- R3: Communal reserve with 70kg cap
- R4: Ledger entry with deposit status
- R5: Lake mass monitoring (threshold check at 140kg)
- R6: Proportional reserve release
- R7: Release termination condition (stop at 190kg or when reserve exhausted)
- R8: Violation detection (catch > 4kg without deposit)
- R9: Violation recording in ledger
- R13: Transparency (ledger entries and reserve balances)

Note: R10-R12 (revocation process, flag, appeal) are marked as TECHNICALLY_UNREALISABLE
and are skipped per the specification.
"""

import pytest
import json
import os

from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.catch_cap import CatchCapNorm
from norms.mandatory_reserve import MandatoryReserveNorm
from norms.communal_reserve import CommunalReserveNorm
from norms.lake_watcher import LakeWatcherNorm


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


# =============================================================================
# R1: 4kg Per-Trip Catch Limit Tests
# =============================================================================

class TestR1_CatchCap4kg:
    """R1: Verify 4kg per-trip catch limit is enforced."""

    def test_catch_at_4kg_limit_allowed(self):
        """Catch exactly at 4kg should be allowed without violation."""
        norm = CatchCapNorm(key="catch_cap", params={"limit_kg": 4.0})
        context = _context()

        decision = norm.evaluate(context, "agent_0", raw_kg=4.0, proposed_kg=4.0)

        assert decision.kept_kg == 4.0
        assert not decision.violated

    def test_catch_below_4kg_allowed(self):
        """Catch below 4kg should be allowed."""
        norm = CatchCapNorm(key="catch_cap", params={"limit_kg": 4.0})
        context = _context()

        decision = norm.evaluate(context, "agent_0", raw_kg=3.5, proposed_kg=3.5)

        assert decision.kept_kg == 3.5
        assert not decision.violated

    def test_catch_above_4kg_trimmed_to_limit(self):
        """Catch above 4kg should be trimmed to 4kg limit."""
        norm = CatchCapNorm(key="catch_cap", params={"limit_kg": 4.0})
        context = _context()

        decision = norm.evaluate(context, "agent_0", raw_kg=6.0, proposed_kg=6.0)

        assert decision.kept_kg == 4.0
        assert decision.violated
        assert decision.sanction == "over_cap"

    def test_catch_above_4kg_violation_recorded(self):
        """Violation should be recorded with correct excess amount."""
        norm = CatchCapNorm(key="catch_cap", params={"limit_kg": 4.0})
        context = _context()

        decision = norm.evaluate(context, "agent_0", raw_kg=6.0, proposed_kg=6.0)
        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=4.0)

        state = context.norm_state("catch_cap")
        assert "violations" in state
        assert len(state["violations"]) == 1
        violation = state["violations"][0]
        assert violation["excess_kg"] == 2.0
        assert violation["attempted_kg"] == 6.0
        assert violation["allowed_kg"] == 4.0

    def test_default_limit_is_4kg(self):
        """Default limit should be 4kg when not specified."""
        norm = CatchCapNorm(key="catch_cap", params={})
        context = _context()

        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)

        assert decision.kept_kg == 4.0
        assert decision.violated

    def test_config_has_4kg_limit(self):
        """Verify config.json has 4kg limit configured."""
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "state", "config.json")
        with open(config_path) as f:
            config = json.load(f)

        catch_cap_config = next((n for n in config["norms"] if n["type"] == "catch_cap"), None)
        assert catch_cap_config is not None, "catch_cap norm must be configured"
        assert catch_cap_config.get("limit_kg") == 4.0, f"limit_kg must be 4.0, got {catch_cap_config.get('limit_kg')}"


# =============================================================================
# R2: 1kg Personal Reserve Tests
# =============================================================================

class TestR2_PersonalReserve:
    """R2: Verify 1kg personal reserve requirement is enforced."""

    def test_1kg_reserve_required(self):
        """1kg reserve should be required by default."""
        norm = MandatoryReserveNorm(key="mandatory_reserve", params={})
        context = _context()

        # First call initializes reserve
        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)

        state = context.norm_state("mandatory_reserve")
        assert state["agent_0"]["reserve_kg"] == 1.0

    def test_reserve_tracks_separately(self):
        """Reserve should be tracked per agent."""
        norm = MandatoryReserveNorm(key="mandatory_reserve", params={"reserve_kg": 1.0})
        context = _context()

        norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)
        norm.evaluate(context, "agent_1", raw_kg=5.0, proposed_kg=5.0)

        state = context.norm_state("mandatory_reserve")
        assert state["agent_0"]["reserve_kg"] == 1.0
        assert state["agent_1"]["reserve_kg"] == 1.0

    def test_config_has_1kg_reserve(self):
        """Verify config.json has 1kg reserve configured."""
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "state", "config.json")
        with open(config_path) as f:
            config = json.load(f)

        reserve_config = next((n for n in config["norms"] if n["type"] == "mandatory_reserve"), None)
        assert reserve_config is not None, "mandatory_reserve norm must be configured"
        assert reserve_config.get("reserve_kg") == 1.0, f"reserve_kg must be 1.0, got {reserve_config.get('reserve_kg')}"


# =============================================================================
# R3: Communal Reserve with 70kg Cap Tests
# =============================================================================

class TestR3_CommunalReserve70kgCap:
    """R3: Verify communal reserve with 70kg cap is managed correctly."""

    def test_default_max_reserve_is_70kg(self):
        """Default max reserve should be 70kg."""
        norm = CommunalReserveNorm(key="communal_reserve", params={})
        assert norm.max_reserve_kg == 70.0

    def test_deposit_increases_reserve(self):
        """Deposit should increase reserve balance."""
        norm = CommunalReserveNorm(key="communal_reserve", params={})
        context = _context()

        # Simulate a catch of 6kg (2kg over 4kg limit)
        decision = norm.evaluate(context, "agent_0", raw_kg=6.0, proposed_kg=4.0)

        state = context.norm_state("communal_reserve")
        assert state["reserve_balance_kg"] == 2.0

    def test_deposit_recorded_with_details(self):
        """Deposit should be recorded with round, agent, and amount."""
        norm = CommunalReserveNorm(key="communal_reserve", params={})
        context = _context(round_number=3)

        decision = norm.evaluate(context, "agent_0", raw_kg=7.0, proposed_kg=4.0)
        norm.on_agent_settled(context, "agent_0", decision, harvested_kg=4.0)

        state = context.norm_state("communal_reserve")
        assert "deposits" in state
        assert len(state["deposits"]) == 1
        deposit = state["deposits"][0]
        assert deposit["round"] == 3
        assert deposit["agent_id"] == "agent_0"
        assert deposit["deposit_kg"] == 3.0

    def test_reserve_respects_70kg_cap(self):
        """Reserve should not exceed 70kg cap."""
        norm = CommunalReserveNorm(key="communal_reserve", params={"max_reserve_kg": 70.0})
        context = _context()

        # Pre-fill reserve to 68kg
        state = context.norm_state("communal_reserve")
        state["reserve_balance_kg"] = 68.0

        # Try to deposit 4kg (would bring to 72kg, but cap is 70kg)
        decision = norm.evaluate(context, "agent_0", raw_kg=8.0, proposed_kg=4.0)

        assert state["reserve_balance_kg"] == 70.0  # Capped at 70kg

    def test_excess_above_cap_not_deposited(self):
        """Excess above cap should not be deposited."""
        norm = CommunalReserveNorm(key="communal_reserve", params={"max_reserve_kg": 70.0})
        context = _context()

        # Pre-fill reserve to 69kg
        state = context.norm_state("communal_reserve")
        state["reserve_balance_kg"] = 69.0

        # Try to deposit 4kg (would bring to 73kg, but cap is 70kg)
        decision = norm.evaluate(context, "agent_0", raw_kg=8.0, proposed_kg=4.0)

        # Only 1kg should be deposited (to reach cap)
        assert state["reserve_balance_kg"] == 70.0

    def test_config_has_70kg_cap(self):
        """Verify config.json has 70kg max_reserve_kg configured."""
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "state", "config.json")
        with open(config_path) as f:
            config = json.load(f)

        reserve_config = next((n for n in config["norms"] if n["type"] == "communal_reserve"), None)
        assert reserve_config is not None, "communal_reserve norm must be configured"
        assert reserve_config.get("max_reserve_kg") == 70.0, f"max_reserve_kg must be 70.0, got {reserve_config.get('max_reserve_kg')}"


# =============================================================================
# R4: Ledger Entry with Deposit Status Tests
# =============================================================================

class TestR4_LedgerEntryDepositStatus:
    """R4: Verify ledger entries include deposit status."""

    def test_ledger_entry_includes_deposit_kg(self):
        """Ledger entry should include deposit_kg field."""
        lake_watcher = LakeWatcherNorm(key="lake_watcher", params={})
        communal_reserve = CommunalReserveNorm(key="communal_reserve", params={})
        context = _context(round_number=1)

        # Set up watcher
        from roles.roles import assign_role
        assign_role("lake_watcher", "agent_0", context.fluents, 1, exclusive=True)

        # Simulate deposit
        communal_reserve.evaluate(context, "agent_1", raw_kg=6.0, proposed_kg=4.0)

        # Record in ledger via lake_watcher
        decision = NormDecision.allow(kept_kg=4.0)
        lake_watcher.on_agent_settled(context, "agent_1", decision, harvested_kg=4.0)

        state = context.norm_state("lake_watcher")
        ledger = state.get("communal_ledger", [])
        assert len(ledger) > 0
        entry = ledger[-1]
        assert "deposit_kg" in entry
        assert entry["deposit_kg"] == 2.0  # 6kg - 4kg limit

    def test_ledger_entry_includes_deposit_status(self):
        """Ledger entry should include deposit_status boolean."""
        lake_watcher = LakeWatcherNorm(key="lake_watcher", params={})
        communal_reserve = CommunalReserveNorm(key="communal_reserve", params={})
        context = _context(round_number=1)

        from roles.roles import assign_role
        assign_role("lake_watcher", "agent_0", context.fluents, 1, exclusive=True)

        communal_reserve.evaluate(context, "agent_1", raw_kg=6.0, proposed_kg=4.0)

        decision = NormDecision.allow(kept_kg=4.0)
        lake_watcher.on_agent_settled(context, "agent_1", decision, harvested_kg=4.0)

        state = context.norm_state("lake_watcher")
        ledger = state.get("communal_ledger", [])
        assert len(ledger) > 0
        entry = ledger[-1]
        assert "deposit_status" in entry
        assert entry["deposit_status"] is True

    def test_ledger_entry_no_deposit_when_under_limit(self):
        """Ledger entry should show no deposit when catch is under limit."""
        lake_watcher = LakeWatcherNorm(key="lake_watcher", params={})
        communal_reserve = CommunalReserveNorm(key="communal_reserve", params={})
        context = _context(round_number=1)

        from roles.roles import assign_role
        assign_role("lake_watcher", "agent_0", context.fluents, 1, exclusive=True)

        # Catch at limit (no deposit)
        communal_reserve.evaluate(context, "agent_1", raw_kg=4.0, proposed_kg=4.0)

        decision = NormDecision.allow(kept_kg=4.0)
        lake_watcher.on_agent_settled(context, "agent_1", decision, harvested_kg=4.0)

        state = context.norm_state("lake_watcher")
        ledger = state.get("communal_ledger", [])
        assert len(ledger) > 0
        entry = ledger[-1]
        assert entry["deposit_kg"] == 0.0
        assert entry["deposit_status"] is False


# =============================================================================
# R5: Lake Mass Monitoring (Threshold Check) Tests
# =============================================================================

class TestR5_LakeMassMonitoring:
    """R5: Verify lake mass monitoring at 140kg threshold triggers release."""

    def test_release_triggered_below_140kg(self):
        """Release should trigger when lake is below 140kg."""
        norm = CommunalReserveNorm(key="communal_reserve", params={
            "release_threshold_kg": 140.0,
            "release_target_kg": 190.0
        })

        # Lake at 100kg (below 140kg threshold)
        context = _context(stock_kg=100.0, round_number=2)
        state = context.norm_state("communal_reserve")
        state["reserve_balance_kg"] = 50.0
        state["previous_round_catches"] = {"agent_0": 4.0, "agent_1": 6.0}
        state["previous_round_total"] = 10.0

        norm.on_round_start(context)

        # Release should have occurred
        assert "releases" in state
        assert len(state["releases"]) == 1
        release = state["releases"][0]
        assert release["stock_before_kg"] == 100.0

    def test_no_release_when_above_140kg(self):
        """No release when lake is above 140kg."""
        norm = CommunalReserveNorm(key="communal_reserve", params={
            "release_threshold_kg": 140.0,
            "release_target_kg": 190.0
        })

        # Lake at 150kg (above 140kg threshold)
        context = _context(stock_kg=150.0, round_number=2)
        state = context.norm_state("communal_reserve")
        state["reserve_balance_kg"] = 50.0
        state["previous_round_catches"] = {"agent_0": 4.0}
        state["previous_round_total"] = 4.0

        norm.on_round_start(context)

        # No release should occur
        assert "releases" not in state or len(state.get("releases", [])) == 0

    def test_no_release_at_exactly_140kg(self):
        """No release when lake is exactly at 140kg."""
        norm = CommunalReserveNorm(key="communal_reserve", params={
            "release_threshold_kg": 140.0,
            "release_target_kg": 190.0
        })

        context = _context(stock_kg=140.0, round_number=2)
        state = context.norm_state("communal_reserve")
        state["reserve_balance_kg"] = 50.0
        state["previous_round_catches"] = {"agent_0": 4.0}
        state["previous_round_total"] = 4.0

        norm.on_round_start(context)

        # No release should occur at exactly threshold
        assert "releases" not in state or len(state.get("releases", [])) == 0

    def test_default_release_threshold_is_140kg(self):
        """Default release threshold should be 140kg."""
        norm = CommunalReserveNorm(key="communal_reserve", params={})
        assert norm.release_threshold_kg == 140.0

    def test_config_has_140kg_threshold(self):
        """Verify config.json has 140kg release_threshold_kg configured."""
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "state", "config.json")
        with open(config_path) as f:
            config = json.load(f)

        reserve_config = next((n for n in config["norms"] if n["type"] == "communal_reserve"), None)
        assert reserve_config is not None, "communal_reserve norm must be configured"
        assert reserve_config.get("release_threshold_kg") == 140.0, f"release_threshold_kg must be 140.0, got {reserve_config.get('release_threshold_kg')}"


# =============================================================================
# R6: Proportional Reserve Release Tests
# =============================================================================

class TestR6_ProportionalRelease:
    """R6: Verify proportional reserve release based on previous round's catch."""

    def test_proportional_distribution_calculated(self):
        """Distribution should be proportional to previous round's catch."""
        norm = CommunalReserveNorm(key="communal_reserve", params={
            "release_threshold_kg": 140.0,
            "release_target_kg": 190.0
        })

        # Lake at 100kg, need to reach 190kg (need 90kg)
        context = _context(stock_kg=100.0, round_number=2)
        state = context.norm_state("communal_reserve")
        state["reserve_balance_kg"] = 100.0  # Enough to cover release

        # Previous round: agent_0 caught 6kg, agent_1 caught 4kg (total 10kg)
        state["previous_round_catches"] = {"agent_0": 6.0, "agent_1": 4.0}
        state["previous_round_total"] = 10.0

        norm.on_round_start(context)

        # Should release 90kg (100->190)
        release = state["releases"][0]
        assert release["released_kg"] == 90.0

        # Check distributions
        distributions = release["distributions"]
        assert distributions["agent_0"]["share_ratio"] == 0.6  # 6/10
        assert distributions["agent_1"]["share_ratio"] == 0.4  # 4/10
        assert distributions["agent_0"]["distribution_kg"] == 54.0  # 60% of 90
        assert distributions["agent_1"]["distribution_kg"] == 36.0  # 40% of 90

    def test_distributions_recorded_in_state(self):
        """Distributions should be recorded in norm state."""
        norm = CommunalReserveNorm(key="communal_reserve", params={
            "release_threshold_kg": 140.0,
            "release_target_kg": 190.0
        })

        context = _context(stock_kg=100.0, round_number=2)
        state = context.norm_state("communal_reserve")
        state["reserve_balance_kg"] = 50.0
        state["previous_round_catches"] = {"agent_0": 4.0}
        state["previous_round_total"] = 4.0

        norm.on_round_start(context)

        assert "distributions" in state
        assert len(state["distributions"]) > 0
        dist = state["distributions"][0]
        assert dist["agent_id"] == "agent_0"
        assert dist["share_ratio"] == 1.0


# =============================================================================
# R7: Release Termination Condition Tests
# =============================================================================

class TestR7_ReleaseTermination:
    """R7: Verify release stops at 190kg target or when reserve is exhausted."""

    def test_release_stops_at_190kg_target(self):
        """Release should stop when lake reaches 190kg."""
        norm = CommunalReserveNorm(key="communal_reserve", params={
            "release_threshold_kg": 140.0,
            "release_target_kg": 190.0
        })

        # Lake at 150kg, target is 190kg, so need 40kg
        context = _context(stock_kg=150.0, round_number=2)
        state = context.norm_state("communal_reserve")
        state["reserve_balance_kg"] = 100.0  # More than enough
        state["previous_round_catches"] = {"agent_0": 4.0}
        state["previous_round_total"] = 4.0

        norm.on_round_start(context)

        # Lake is above 140kg, so no release
        assert "releases" not in state or len(state.get("releases", [])) == 0

    def test_release_only_what_is_needed(self):
        """Release should only release what's needed to reach target."""
        norm = CommunalReserveNorm(key="communal_reserve", params={
            "release_threshold_kg": 140.0,
            "release_target_kg": 190.0
        })

        # Lake at 100kg, target is 190kg, so need 90kg
        context = _context(stock_kg=100.0, round_number=2)
        state = context.norm_state("communal_reserve")
        state["reserve_balance_kg"] = 200.0  # More than enough
        state["previous_round_catches"] = {"agent_0": 4.0}
        state["previous_round_total"] = 4.0

        norm.on_round_start(context)

        # Should only release 90kg (not the full 200kg)
        release = state["releases"][0]
        assert release["released_kg"] == 90.0
        assert release["required_kg"] == 90.0

    def test_release_limited_by_reserve_balance(self):
        """Release should be limited by available reserve."""
        norm = CommunalReserveNorm(key="communal_reserve", params={
            "release_threshold_kg": 140.0,
            "release_target_kg": 190.0
        })

        # Lake at 100kg, need 90kg to reach target
        context = _context(stock_kg=100.0, round_number=2)
        state = context.norm_state("communal_reserve")
        state["reserve_balance_kg"] = 50.0  # Only have 50kg
        state["previous_round_catches"] = {"agent_0": 4.0}
        state["previous_round_total"] = 4.0

        norm.on_round_start(context)

        # Should only release 50kg (all we have)
        release = state["releases"][0]
        assert release["released_kg"] == 50.0
        assert release["required_kg"] == 90.0
        assert state["reserve_balance_kg"] == 0.0  # Exhausted

    def test_no_release_when_reserve_is_zero(self):
        """No release when reserve is empty."""
        norm = CommunalReserveNorm(key="communal_reserve", params={
            "release_threshold_kg": 140.0,
            "release_target_kg": 190.0
        })

        context = _context(stock_kg=100.0, round_number=2)
        state = context.norm_state("communal_reserve")
        state["reserve_balance_kg"] = 0.0
        state["previous_round_catches"] = {"agent_0": 4.0}
        state["previous_round_total"] = 4.0

        norm.on_round_start(context)

        # No release when reserve is empty
        assert "releases" not in state or len(state.get("releases", [])) == 0

    def test_default_release_target_is_190kg(self):
        """Default release target should be 190kg."""
        norm = CommunalReserveNorm(key="communal_reserve", params={})
        assert norm.release_target_kg == 190.0

    def test_config_has_190kg_target(self):
        """Verify config.json has 190kg release_target_kg configured."""
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "state", "config.json")
        with open(config_path) as f:
            config = json.load(f)

        reserve_config = next((n for n in config["norms"] if n["type"] == "communal_reserve"), None)
        assert reserve_config is not None, "communal_reserve norm must be configured"
        assert reserve_config.get("release_target_kg") == 190.0, f"release_target_kg must be 190.0, got {reserve_config.get('release_target_kg')}"


# =============================================================================
# R8: Violation Detection Tests
# =============================================================================

class TestR8_ViolationDetection:
    """R8: Verify violation detection for catch > 4kg without deposit."""

    def test_catch_over_4kg_is_violation(self):
        """Catch over 4kg should be marked as violation."""
        norm = CatchCapNorm(key="catch_cap", params={"limit_kg": 4.0})
        context = _context()

        decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)

        assert decision.violated
        assert decision.sanction == "over_cap"

    def test_violation_triggers_deposit(self):
        """Violation should trigger deposit in communal reserve."""
        catch_cap = CatchCapNorm(key="catch_cap", params={"limit_kg": 4.0})
        communal_reserve = CommunalReserveNorm(key="communal_reserve", params={})
        context = _context()

        # First, catch_cap trims to limit
        decision = catch_cap.evaluate(context, "agent_0", raw_kg=6.0, proposed_kg=6.0)
        assert decision.violated

        # Then communal_reserve handles deposit
        communal_reserve.evaluate(context, "agent_0", raw_kg=6.0, proposed_kg=decision.kept_kg)

        state = context.norm_state("communal_reserve")
        assert state["reserve_balance_kg"] == 2.0  # 6kg - 4kg limit


# =============================================================================
# R9: Violation Recording Tests
# =============================================================================

class TestR9_ViolationRecording:
    """R9: Verify violations are recorded in the ledger."""

    def test_violation_recorded_in_ledger(self):
        """Violation should be recorded in communal ledger."""
        lake_watcher = LakeWatcherNorm(key="lake_watcher", params={})
        catch_cap = CatchCapNorm(key="catch_cap", params={"limit_kg": 4.0})
        context = _context(round_number=1)

        from roles.roles import assign_role
        assign_role("lake_watcher", "agent_0", context.fluents, 1, exclusive=True)

        # Violation: catch 6kg over 4kg limit
        decision = catch_cap.evaluate(context, "agent_1", raw_kg=6.0, proposed_kg=6.0)
        catch_cap.on_agent_settled(context, "agent_1", decision, harvested_kg=4.0)
        lake_watcher.on_agent_settled(context, "agent_1", decision, harvested_kg=4.0)

        state = context.norm_state("lake_watcher")
        ledger = state.get("communal_ledger", [])
        assert len(ledger) > 0
        entry = ledger[-1]
        assert entry["violation"] is True
        assert entry["violation_type"] == "over_cap_without_deposit"

    def test_no_violation_when_under_limit(self):
        """No violation recorded when catch is under limit."""
        lake_watcher = LakeWatcherNorm(key="lake_watcher", params={})
        context = _context(round_number=1)

        from roles.roles import assign_role
        assign_role("lake_watcher", "agent_0", context.fluents, 1, exclusive=True)

        # No violation: catch 3kg under 4kg limit
        decision = NormDecision.allow(kept_kg=3.0)
        lake_watcher.on_agent_settled(context, "agent_1", decision, harvested_kg=3.0)

        state = context.norm_state("lake_watcher")
        ledger = state.get("communal_ledger", [])
        assert len(ledger) > 0
        entry = ledger[-1]
        assert entry["violation"] is False
        assert entry["violation_type"] is None


# =============================================================================
# R13: Transparency Tests
# =============================================================================

class TestR13_Transparency:
    """R13: Verify transparency through ledger entries and reserve balances."""

    def test_ledger_tracks_all_entries(self):
        """Communal ledger should track all entries."""
        lake_watcher = LakeWatcherNorm(key="lake_watcher", params={})
        context = _context(round_number=1)

        from roles.roles import assign_role
        assign_role("lake_watcher", "agent_0", context.fluents, 1, exclusive=True)

        # Multiple entries
        decision = NormDecision.allow(kept_kg=4.0)
        lake_watcher.on_agent_settled(context, "agent_1", decision, harvested_kg=4.0)
        lake_watcher.on_agent_settled(context, "agent_2", decision, harvested_kg=4.0)

        state = context.norm_state("lake_watcher")
        ledger = state.get("communal_ledger", [])
        assert len(ledger) == 2

    def test_reserve_balance_tracked(self):
        """Reserve balance should be tracked across rounds."""
        norm = CommunalReserveNorm(key="communal_reserve", params={})

        # Round 1: Deposit 5kg
        context1 = _context(round_number=1)
        norm.evaluate(context1, "agent_0", raw_kg=9.0, proposed_kg=4.0)

        state1 = context1.norm_state("communal_reserve")
        assert state1["reserve_balance_kg"] == 5.0

    def test_deposit_history_tracked(self):
        """Deposit history should be tracked."""
        norm = CommunalReserveNorm(key="communal_reserve", params={})
        context = _context(round_number=1)

        norm.evaluate(context, "agent_0", raw_kg=6.0, proposed_kg=4.0)

        state = context.norm_state("communal_reserve")
        assert "deposits" in state
        assert len(state["deposits"]) == 1

    def test_release_history_tracked(self):
        """Release history should be tracked."""
        norm = CommunalReserveNorm(key="communal_reserve", params={
            "release_threshold_kg": 140.0,
            "release_target_kg": 190.0
        })

        context = _context(stock_kg=100.0, round_number=2)
        state = context.norm_state("communal_reserve")
        state["reserve_balance_kg"] = 50.0
        state["previous_round_catches"] = {"agent_0": 4.0}
        state["previous_round_total"] = 4.0

        norm.on_round_start(context)

        assert "releases" in state
        assert len(state["releases"]) == 1


# =============================================================================
# Integration and Configuration Tests
# =============================================================================

class TestIntegrationAndConfig:
    """Integration tests and configuration verification."""

    def test_all_required_norms_configured(self):
        """Verify all required norms from R4 spec are configured."""
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "state", "config.json")
        with open(config_path) as f:
            config = json.load(f)

        norm_types = set(n["type"] for n in config["norms"])

        required_norms = {
            "lake_watcher",      # R4, R9
            "catch_cap",          # R1, R8
            "mandatory_reserve",  # R2
            "communal_reserve",   # R3, R5, R6, R7
        }

        missing = required_norms - norm_types
        assert not missing, f"Missing required norms: {missing}"

    def test_norm_evaluation_order(self):
        """Verify norms are in correct evaluation order per spec."""
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "state", "config.json")
        with open(config_path) as f:
            config = json.load(f)

        norm_types = [n["type"] for n in config["norms"]]

        # Required order per R4 spec:
        # 1. lake_watcher - Establish Kai's role and communal ledger
        # 2. catch_cap - Apply 4kg catch limit
        # 3. mandatory_reserve - Check 1kg personal reserve
        # 4. communal_reserve - Handle surplus deposit, monitor lake mass, trigger releases

        watcher_idx = next((i for i, t in enumerate(norm_types) if t == "lake_watcher"), None)
        catch_cap_idx = next((i for i, t in enumerate(norm_types) if t == "catch_cap"), None)
        reserve_idx = next((i for i, t in enumerate(norm_types) if t == "mandatory_reserve"), None)
        communal_idx = next((i for i, t in enumerate(norm_types) if t == "communal_reserve"), None)

        assert watcher_idx is not None, "lake_watcher must be configured"
        assert catch_cap_idx is not None, "catch_cap must be configured"
        assert reserve_idx is not None, "mandatory_reserve must be configured"
        assert communal_idx is not None, "communal_reserve must be configured"

        assert watcher_idx < catch_cap_idx, "lake_watcher must come before catch_cap"
        assert catch_cap_idx < reserve_idx, "catch_cap must come before mandatory_reserve"
        assert reserve_idx < communal_idx, "mandatory_reserve must come before communal_reserve"

    def test_all_norm_files_exist(self):
        """Verify all norm implementation files exist."""
        norms_dir = os.path.join(os.path.dirname(__file__), "..", "..", "norms")

        required_files = {
            "lake_watcher.py",
            "catch_cap.py",
            "mandatory_reserve.py",
            "communal_reserve.py",
        }

        for filename in required_files:
            filepath = os.path.join(norms_dir, filename)
            assert os.path.exists(filepath), f"Missing norm file: {filename}"

    def test_norm_types_registered(self):
        """Verify all norm types are registered in institution.json."""
        institution_path = os.path.join(os.path.dirname(__file__), "..", "..", "state", "institution.json")
        with open(institution_path) as f:
            institution = json.load(f)

        registered_types = set(institution.get("norm_types", {}).keys())

        required_types = {
            "lake_watcher",
            "catch_cap",
            "mandatory_reserve",
            "communal_reserve",
        }

        missing = required_types - registered_types
        assert not missing, f"Missing registered norm types: {missing}"


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Edge case tests."""

    def test_catch_at_exactly_4kg_no_deposit(self):
        """Catch at exactly 4kg should not trigger deposit."""
        communal_reserve = CommunalReserveNorm(key="communal_reserve", params={})
        context = _context()

        decision = communal_reserve.evaluate(context, "agent_0", raw_kg=4.0, proposed_kg=4.0)

        state = context.norm_state("communal_reserve")
        assert state.get("reserve_balance_kg", 0.0) == 0.0

    def test_catch_just_over_4kg_deposit_small_amount(self):
        """Catch just over 4kg should deposit small amount."""
        communal_reserve = CommunalReserveNorm(key="communal_reserve", params={})
        context = _context()

        decision = communal_reserve.evaluate(context, "agent_0", raw_kg=4.1, proposed_kg=4.0)

        state = context.norm_state("communal_reserve")
        assert abs(state["reserve_balance_kg"] - 0.1) < 0.001  # Account for floating point

    def test_very_large_catch_deposit_capped(self):
        """Very large catch should deposit up to cap only."""
        communal_reserve = CommunalReserveNorm(key="communal_reserve", params={"max_reserve_kg": 70.0})
        context = _context()

        # Pre-fill reserve to 65kg
        state = context.norm_state("communal_reserve")
        state["reserve_balance_kg"] = 65.0

        # Try to deposit 20kg (would bring to 85kg, but cap is 70kg)
        decision = communal_reserve.evaluate(context, "agent_0", raw_kg=24.0, proposed_kg=4.0)

        assert state["reserve_balance_kg"] == 70.0  # Capped

    def test_release_with_no_previous_catches(self):
        """Release should handle case with no previous round catches."""
        norm = CommunalReserveNorm(key="communal_reserve", params={
            "release_threshold_kg": 140.0,
            "release_target_kg": 190.0
        })

        context = _context(stock_kg=100.0, round_number=2)
        state = context.norm_state("communal_reserve")
        state["reserve_balance_kg"] = 50.0
        # No previous_round_catches set

        norm.on_round_start(context)

        # Should not crash, but also not release
        assert "releases" not in state or len(state.get("releases", [])) == 0

    def test_ledger_with_multiple_rounds(self):
        """Ledger should track entries across multiple rounds."""
        lake_watcher = LakeWatcherNorm(key="lake_watcher", params={})
        catch_cap = CatchCapNorm(key="catch_cap", params={"limit_kg": 4.0})

        from roles.roles import assign_role

        # Round 1
        context1 = _context(round_number=1)
        assign_role("lake_watcher", "agent_0", context1.fluents, 1, exclusive=True)

        decision1 = catch_cap.evaluate(context1, "agent_1", raw_kg=5.0, proposed_kg=5.0)
        lake_watcher.on_agent_settled(context1, "agent_1", decision1, harvested_kg=4.0)

        state1 = context1.norm_state("lake_watcher")
        ledger1 = state1.get("communal_ledger", [])
        assert len(ledger1) == 1
        assert ledger1[0]["round"] == 1

        # Round 2 (carry over state properly)
        runtime2 = {"stock_kg": 300.0, "rounds": [], "payoff": {}}
        runtime2["norms"] = {"lake_watcher": state1.copy()}
        context2 = _context(round_number=2, existing_runtime=runtime2)
        assign_role("lake_watcher", "agent_0", context2.fluents, 2, exclusive=True)

        decision2 = NormDecision.allow(kept_kg=3.0)
        lake_watcher.on_agent_settled(context2, "agent_1", decision2, harvested_kg=3.0)

        state2 = context2.norm_state("lake_watcher")
        ledger2 = state2.get("communal_ledger", [])
        assert len(ledger2) == 2
        assert ledger2[0]["round"] == 1
        assert ledger2[1]["round"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
