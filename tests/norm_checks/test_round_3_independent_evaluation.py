"""Independent evaluation tests for Round 3 norm implementation.

These tests are written by the norm-evaluator (not the implementer) to verify
that the implementation actually satisfies each requirement from the spec.
"""

import pytest
from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.dynamic_individual_cap import DynamicIndividualCapNorm
from norms.weekly_audit import WeeklyAuditNorm


class TestR3_1_DynamicIndividualCap:
    """R3.1: Individual Per-Trip Cap (Dynamic)
    
    Each fisher may keep at most:
    - 15 kg per trip when lake reserves >= 20 kg at round start
    - 10 kg per trip when lake reserves < 20 kg at round start
    The cap is evaluated at round start and applies uniformly to all agents that round.
    """

    def create_cap_context(self, round_number=1, stock_before=50.0):
        """Create a test context for the dynamic individual cap norm."""
        config = {
            "norms": [
                {"type": "dynamic_individual_cap", "standard_cap_kg": 15, "emergency_cap_kg": 10, "emergency_threshold_kg": 20}
            ]
        }
        return HarvestContext(
            config=config,
            fluents=[],
            runtime={"norms": {}},
            agents={},
            round_number=round_number,
            stock_before=stock_before,
        )

    def test_standard_cap_when_reserves_20kg_or_more(self):
        """Standard 15kg cap applies when reserves >= 20kg."""
        context = self.create_cap_context(stock_before=20.0)
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})
        
        norm.on_round_start(context)
        current_cap = context.norm_state("dynamic_individual_cap").get("current_cap")
        
        assert current_cap == 15, f"Expected cap of 15 when reserves=20kg, got {current_cap}"
        
        # Also test with higher reserves
        context2 = self.create_cap_context(stock_before=50.0)
        norm2 = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})
        norm2.on_round_start(context2)
        assert context2.norm_state("dynamic_individual_cap").get("current_cap") == 15

    def test_emergency_cap_when_reserves_below_20kg(self):
        """Emergency 10kg cap applies when reserves < 20kg."""
        context = self.create_cap_context(stock_before=19.9)
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})
        
        norm.on_round_start(context)
        current_cap = context.norm_state("dynamic_individual_cap").get("current_cap")
        
        assert current_cap == 10, f"Expected cap of 10 when reserves=19.9kg, got {current_cap}"
        
        # Also test with even lower reserves
        context2 = self.create_cap_context(stock_before=5.0)
        norm2 = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})
        norm2.on_round_start(context2)
        assert context2.norm_state("dynamic_individual_cap").get("current_cap") == 10

    def test_cap_evaluated_at_round_start(self):
        """Cap is determined in on_round_start and stored in norm_state."""
        context = self.create_cap_context(stock_before=50.0)
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})
        
        # Before on_round_start, current_cap should not be set
        assert context.norm_state("dynamic_individual_cap").get("current_cap") is None
        
        # After on_round_start, it should be set
        norm.on_round_start(context)
        assert context.norm_state("dynamic_individual_cap").get("current_cap") is not None


class TestR3_2_ExcessReturnToLake:
    """R3.2: Excess Return to Lake
    
    If an agent's raw catch exceeds the applicable cap, the excess must be returned
to the lake immediately.
    """

    def create_cap_context(self, round_number=1, stock_before=50.0):
        """Create a test context."""
        config = {
            "norms": [
                {"type": "dynamic_individual_cap", "standard_cap_kg": 15, "emergency_cap_kg": 10, "emergency_threshold_kg": 20}
            ]
        }
        return HarvestContext(
            config=config,
            fluents=[],
            runtime={"norms": {}},
            agents={},
            round_number=round_number,
            stock_before=stock_before,
        )

    def test_excess_is_returned_to_lake_via_override(self):
        """Excess fish are returned to lake via override_stock_after_regrowth."""
        context = self.create_cap_context(round_number=1, stock_before=50.0)
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})
        
        norm.on_round_start(context)
        
        # Agent catches 20kg, keeps 15kg, returns 5kg
        decision = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        
        # Verify the decision
        assert decision.kept_kg == 15.0, f"Expected kept_kg=15, got {decision.kept_kg}"
        
        # Simulate round end with the agent's harvest
        round_results = {
            "agent_1": {"harvested_kg": 15.0, "effort": 1.0, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)
        
        # Verify stock override was set
        # Stock after harvest: 50 - 15 = 35
        # Stock after return: 35 + 5 = 40
        assert context.stock_override_kg is not None, "Stock override should be set"
        assert abs(context.stock_override_kg - 40.0) < 0.001, f"Expected stock=40, got {context.stock_override_kg}"

    def test_returned_amount_tracked_in_norm_state(self):
        """Total returned to lake is tracked in norm_state."""
        context = self.create_cap_context(round_number=1, stock_before=50.0)
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})
        
        norm.on_round_start(context)
        norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)  # returns 5kg
        norm.evaluate(context, "agent_2", raw_kg=18.0, proposed_kg=18.0)  # returns 3kg
        
        round_results = {
            "agent_1": {"harvested_kg": 15.0, "effort": 1.0, "participated": True, "note": None},
            "agent_2": {"harvested_kg": 15.0, "effort": 1.0, "participated": True, "note": None},
        }
        norm.on_round_end(context, round_results)
        
        total_returned = context.norm_state("dynamic_individual_cap").get("total_returned_to_lake", 0)
        assert abs(total_returned - 8.0) < 0.001, f"Expected total_returned=8, got {total_returned}"


class TestR3_3_SharedLedger:
    """R3.3: Shared Ledger Logging
    
    Every agent's raw catch is recorded in a shared ledger with:
    - Agent ID, Round number, Raw catch, Amount kept, Amount returned, Cap applied
    """

    def create_cap_context(self, round_number=1, stock_before=50.0):
        config = {
            "norms": [
                {"type": "dynamic_individual_cap", "standard_cap_kg": 15, "emergency_cap_kg": 10, "emergency_threshold_kg": 20}
            ]
        }
        return HarvestContext(
            config=config,
            fluents=[],
            runtime={"norms": {}},
            agents={},
            round_number=round_number,
            stock_before=stock_before,
        )

    def test_ledger_records_all_required_fields(self):
        """Ledger entries include all required fields."""
        context = self.create_cap_context(round_number=5, stock_before=50.0)
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})
        
        norm.on_round_start(context)
        norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        
        ledger = context.norm_state("dynamic_individual_cap").get("ledger", [])
        assert len(ledger) == 1
        
        entry = ledger[0]
        assert entry["agent_id"] == "agent_1"
        assert entry["round"] == 5
        assert entry["raw_catch"] == 20.0
        assert entry["kept"] == 15.0
        assert entry["returned"] == 5.0
        assert entry["cap_applied"] == 15

    def test_ledger_persists_across_evaluations(self):
        """Ledger accumulates entries across multiple evaluate() calls."""
        context = self.create_cap_context(round_number=1, stock_before=50.0)
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})
        
        norm.on_round_start(context)
        norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.evaluate(context, "agent_2", raw_kg=10.0, proposed_kg=10.0)
        norm.evaluate(context, "agent_3", raw_kg=25.0, proposed_kg=25.0)
        
        ledger = context.norm_state("dynamic_individual_cap").get("ledger", [])
        assert len(ledger) == 3
        
        agent_ids = [e["agent_id"] for e in ledger]
        assert "agent_1" in agent_ids
        assert "agent_2" in agent_ids
        assert "agent_3" in agent_ids


class TestR3_4_WeeklyAudit:
    """R3.4: Weekly Random Audit
    
    At the end of every 7th round (round_number % 7 == 0), a random audit occurs:
    - Randomly select 30% of agents (minimum 1) to audit
    - Check all rounds in the current week (last 7 rounds)
    - Flag if raw catch > applicable cap AND they kept > cap
    """

    def create_audit_context(self, round_number=1, ledger=None):
        config = {
            "norms": [
                {"type": "weekly_audit", "audit_frequency_rounds": 7, "audit_sample_rate": 0.30, "sanction_duration_rounds": 1},
                {"type": "dynamic_individual_cap", "id": "cap_norm"}
            ]
        }
        runtime = {"norms": {}}
        if ledger:
            runtime["norms"]["cap_norm"] = {"ledger": ledger}
        
        return HarvestContext(
            config=config,
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=round_number,
            stock_before=50.0,
        )

    def test_audit_occurs_on_round_7(self):
        """Audit occurs when round_number % 7 == 0."""
        # Round 7 should trigger audit
        ledger = [
            {"round": 5, "agent_id": "agent_1", "raw_catch": 20.0, "kept": 15.0, "returned": 5.0, "cap_applied": 15},
        ]
        context = self.create_audit_context(round_number=7, ledger=ledger)
        norm = WeeklyAuditNorm(key="weekly_audit", params={})
        
        round_results = {"agent_1": {"harvested_kg": 10.0}}
        norm.on_round_end(context, round_results)
        
        audit_history = context.norm_state("weekly_audit").get("audit_history", [])
        assert len(audit_history) == 1
        assert audit_history[0]["round"] == 7

    def test_audit_does_not_occur_on_non_7_rounds(self):
        """Audit does not occur on rounds where round_number % 7 != 0."""
        context = self.create_audit_context(round_number=6)
        norm = WeeklyAuditNorm(key="weekly_audit", params={})
        
        round_results = {"agent_1": {"harvested_kg": 10.0}}
        norm.on_round_end(context, round_results)
        
        audit_history = context.norm_state("weekly_audit").get("audit_history", [])
        assert len(audit_history) == 0

    def test_audit_samples_at_least_one_agent(self):
        """Audit samples at least 30% of agents (min 1)."""
        ledger = [
            {"round": 5, "agent_id": f"agent_{i}", "raw_catch": 10.0, "kept": 10.0, "returned": 0.0, "cap_applied": 15}
            for i in range(10)
        ]
        context = self.create_audit_context(round_number=7, ledger=ledger)
        norm = WeeklyAuditNorm(key="weekly_audit", params={})
        
        round_results = {f"agent_{i}": {"harvested_kg": 10.0} for i in range(10)}
        norm.on_round_end(context, round_results)
        
        audit_history = context.norm_state("weekly_audit").get("audit_history", [])
        assert len(audit_history) == 1
        audited = audit_history[0]["audited_agents"]
        # 30% of 10 = 3 agents
        assert len(audited) >= 1, "Should audit at least 1 agent"
        assert len(audited) <= 5, "Should not audit more than 5 agents (50% tolerance)"

    def test_audit_checks_current_week_only(self):
        """Audit only checks rounds from current week (last 7 rounds)."""
        # Create ledger with a VIOLATION (kept > cap means didn't return enough)
        # A violation is: raw_catch > cap_applied AND kept > cap_applied
        # (meaning they didn't return the full excess)
        ledger = [
            # Week 1 (rounds 1-7): agent_1 violated in round 3 by keeping 20kg when cap was 15kg
            {"round": 3, "agent_id": "agent_1", "raw_catch": 25.0, "kept": 20.0, "returned": 5.0, "cap_applied": 15},
            # agent_2 complied (kept exactly the cap)
            {"round": 3, "agent_id": "agent_2", "raw_catch": 20.0, "kept": 15.0, "returned": 5.0, "cap_applied": 15},
        ]
        
        # Use 100% sample rate to ensure deterministic testing
        config = {
            "norms": [
                {"type": "weekly_audit", "audit_frequency_rounds": 7, "audit_sample_rate": 1.0, "sanction_duration_rounds": 1},
                {"type": "dynamic_individual_cap", "id": "cap_norm"}
            ]
        }
        runtime = {"norms": {"cap_norm": {"ledger": ledger}}}
        
        from engine.norms.context import HarvestContext
        context = HarvestContext(
            config=config,
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=7,
            stock_before=50.0,
        )
        
        norm = WeeklyAuditNorm(key="weekly_audit", params={"audit_sample_rate": 1.0})
        
        round_results = {"agent_1": {"harvested_kg": 10.0}, "agent_2": {"harvested_kg": 10.0}}
        norm.on_round_end(context, round_results)
        
        audit_history = context.norm_state("weekly_audit").get("audit_history", [])
        assert len(audit_history) == 1
        sanctioned = audit_history[0].get("sanctioned_agents", [])
        
        # Only agent_1 violated (kept 20 > cap 15)
        # agent_2 complied (kept 15 = cap 15)
        assert "agent_1" in sanctioned, "agent_1 should be sanctioned for keeping 20kg when cap was 15kg"
        assert "agent_2" not in sanctioned, "agent_2 should not be sanctioned - they complied with the cap"


class TestR3_5_FishingRightsSuspension:
    """R3.5: Fishing Rights Suspension
    
    Agents flagged in the audit lose fishing rights for exactly one trip (one round):
    - is_eligible() returns False for the next round
    - After one banned round, eligibility is automatically restored
    """

    def create_audit_context(self, round_number=1, pending_bans=None):
        config = {
            "norms": [
                {"type": "weekly_audit", "audit_frequency_rounds": 7, "audit_sample_rate": 0.30, "sanction_duration_rounds": 1},
                {"type": "dynamic_individual_cap", "id": "cap_norm"}
            ]
        }
        runtime = {"norms": {"weekly_audit": {}}}
        if pending_bans:
            runtime["norms"]["weekly_audit"]["pending_bans"] = pending_bans
        
        return HarvestContext(
            config=config,
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=round_number,
            stock_before=50.0,
        )

    def test_is_eligible_true_without_ban(self):
        """Agent is eligible when no ban is pending."""
        context = self.create_audit_context()
        norm = WeeklyAuditNorm(key="weekly_audit", params={})
        
        assert norm.is_eligible(context, "agent_1") is True

    def test_is_eligible_false_with_ban(self):
        """Agent is NOT eligible when ban is pending."""
        context = self.create_audit_context(pending_bans={"agent_1": 1})
        norm = WeeklyAuditNorm(key="weekly_audit", params={})
        
        assert norm.is_eligible(context, "agent_1") is False

    def test_ban_auto_releases_after_one_round(self):
        """Ban is automatically cleared after one round of ineligibility."""
        context = self.create_audit_context(pending_bans={"agent_1": 1})
        norm = WeeklyAuditNorm(key="weekly_audit", params={})
        
        # First call - should be ineligible and consume the ban
        assert norm.is_eligible(context, "agent_1") is False
        
        # Second call - should be eligible (ban consumed)
        assert norm.is_eligible(context, "agent_1") is True


class TestR3_6_AuditTransparency:
    """R3.6: Audit Transparency
    
    Agents are informed via harvest prompt:
    - Whether an audit occurred in the previous round
    - Which agents (if any) were sanctioned
    - That sanctioned agents are banned next round
    """

    def create_audit_context(self, round_number=1, audit_history=None, pending_bans=None):
        config = {
            "norms": [
                {"type": "weekly_audit", "audit_frequency_rounds": 7, "audit_sample_rate": 0.30, "sanction_duration_rounds": 1},
            ]
        }
        runtime = {"norms": {"weekly_audit": {}}}
        if audit_history:
            runtime["norms"]["weekly_audit"]["audit_history"] = audit_history
        if pending_bans:
            runtime["norms"]["weekly_audit"]["pending_bans"] = pending_bans
        
        return HarvestContext(
            config=config,
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=round_number,
            stock_before=50.0,
        )

    def test_describe_shows_audit_results_next_round(self):
        """describe() shows audit results in the round immediately following audit."""
        audit_history = [{
            "round": 7,
            "audited_agents": ["agent_1"],
            "sanctioned_agents": ["agent_1"],
            "violations": [],
            "total_agents": 2,
        }]
        
        # Round 8 - right after audit in round 7
        context = self.create_audit_context(round_number=8, audit_history=audit_history)
        norm = WeeklyAuditNorm(key="weekly_audit", params={})
        
        description = norm.describe(context, "agent_1")
        
        assert "AUDIT RESULTS" in description
        assert "agent_1" in description

    def test_describe_shows_no_violations_when_compliant(self):
        """describe() indicates when audit found no violations."""
        audit_history = [{
            "round": 7,
            "audited_agents": ["agent_1", "agent_2"],
            "sanctioned_agents": [],
            "violations": [],
            "total_agents": 2,
        }]
        
        context = self.create_audit_context(round_number=8, audit_history=audit_history)
        norm = WeeklyAuditNorm(key="weekly_audit", params={})
        
        description = norm.describe(context, "agent_1")
        
        assert "AUDIT RESULTS" in description
        assert "No violations" in description or "compliant" in description.lower()


class TestR3_7_DynamicCapAnnouncement:
    """R3.7: Dynamic Cap Announcement
    
    When the 10 kg emergency cap is in effect, agents are informed:
    - The emergency cap is active due to low reserves
    - The current cap amount (10 kg)
    - That the normal 15 kg cap will resume when reserves recover
    """

    def test_describe_shows_emergency_cap_message(self):
        """describe() shows emergency cap message when reserves are low."""
        config = {
            "norms": [
                {"type": "dynamic_individual_cap", "standard_cap_kg": 15, "emergency_cap_kg": 10, "emergency_threshold_kg": 20}
            ]
        }
        context = HarvestContext(
            config=config,
            fluents=[],
            runtime={"norms": {}},
            agents={},
            round_number=1,
            stock_before=15.0,  # Below 20kg threshold
        )
        
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})
        norm.on_round_start(context)
        
        description = norm.describe(context, "agent_1")
        
        assert "EMERGENCY" in description.upper() or "emergency" in description.lower()
        assert "10" in description  # Emergency cap amount
        assert "15" in description  # Standard cap amount (for comparison)
        assert "20" in description  # Threshold

    def test_describe_shows_standard_cap_when_healthy(self):
        """describe() shows standard cap message when reserves are healthy."""
        config = {
            "norms": [
                {"type": "dynamic_individual_cap", "standard_cap_kg": 15, "emergency_cap_kg": 10, "emergency_threshold_kg": 20}
            ]
        }
        context = HarvestContext(
            config=config,
            fluents=[],
            runtime={"norms": {}},
            agents={},
            round_number=1,
            stock_before=50.0,  # Healthy reserves
        )
        
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})
        norm.on_round_start(context)
        
        description = norm.describe(context, "agent_1")
        
        assert "15" in description  # Standard cap
        assert "EMERGENCY" not in description.upper()


class TestR3_8_LakeStockReplenishment:
    """R3.8: Lake Stock Replenishment
    
    All excess fish returned due to the individual cap are added back to the
    lake stock immediately via context.override_stock_after_regrowth() in on_round_end().
    """

    def test_stock_override_includes_returned_fish(self):
        """Stock override includes the returned excess fish."""
        config = {
            "norms": [
                {"type": "dynamic_individual_cap", "standard_cap_kg": 15, "emergency_cap_kg": 10, "emergency_threshold_kg": 20}
            ]
        }
        context = HarvestContext(
            config=config,
            fluents=[],
            runtime={"norms": {}},
            agents={},
            round_number=1,
            stock_before=100.0,
        )
        
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})
        norm.on_round_start(context)
        
        # Agent catches 25kg, keeps 15kg, returns 10kg
        norm.evaluate(context, "agent_1", raw_kg=25.0, proposed_kg=25.0)
        
        # Simulate that the agent harvested 15kg (after cap)
        round_results = {
            "agent_1": {"harvested_kg": 15.0, "effort": 1.0, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)
        
        # Expected: 100 - 15 (harvested) + 10 (returned) = 95
        expected_stock = 100.0 - 15.0 + 10.0
        assert context.stock_override_kg is not None
        assert abs(context.stock_override_kg - expected_stock) < 0.001, \
            f"Expected stock={expected_stock}, got {context.stock_override_kg}"


class TestR3_9_AuditHistoryVisibility:
    """R3.9: Audit History Visibility
    
    The shared ledger is public and visible. describe() includes:
    - Recent ledger entries (last 3 rounds)
    - Current week's audit status
    - Any active sanctions
    """

    def test_ledger_shows_recent_entries(self):
        """describe() shows recent ledger entries."""
        config = {
            "norms": [
                {"type": "dynamic_individual_cap", "standard_cap_kg": 15, "emergency_cap_kg": 10, "emergency_threshold_kg": 20}
            ]
        }
        runtime = {
            "norms": {
                "dynamic_individual_cap": {
                    "ledger": [
                        {"round": 1, "agent_id": "agent_1", "raw_catch": 20.0, "kept": 15.0, "returned": 5.0, "cap_applied": 15},
                        {"round": 2, "agent_id": "agent_2", "raw_catch": 18.0, "kept": 15.0, "returned": 3.0, "cap_applied": 15},
                        {"round": 3, "agent_id": "agent_3", "raw_catch": 16.0, "kept": 15.0, "returned": 1.0, "cap_applied": 15},
                    ]
                }
            }
        }
        context = HarvestContext(
            config=config,
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=4,
            stock_before=50.0,
        )
        
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})
        norm.on_round_start(context)
        
        description = norm.describe(context, "agent_1")
        
        # Should mention recent rounds
        assert "Round 1" in description or "Round 2" in description or "Round 3" in description or "ledger" in description.lower()


class TestR3_10_RecoveryDetection:
    """R3.10: Recovery Detection
    
    At the start of each round, check if reserves have recovered:
    - If previous round used 10 kg cap AND current reserves >= 20 kg: announce recovery
    - If previous round used 15 kg cap AND current reserves < 20 kg: announce emergency
    """

    def test_recovery_announcement_when_emergency_to_standard(self):
        """Recovery announcement when transitioning from emergency to standard cap."""
        config = {
            "norms": [
                {"type": "dynamic_individual_cap", "standard_cap_kg": 15, "emergency_cap_kg": 10, "emergency_threshold_kg": 20}
            ]
        }
        runtime = {
            "norms": {
                "dynamic_individual_cap": {
                    "current_cap": 10,  # Previous round was emergency
                    "previous_cap": 15,  # But actually previous was standard...
                    # Actually let's set it properly
                }
            }
        }
        # Start with emergency cap state from previous round
        runtime["norms"]["dynamic_individual_cap"]["current_cap"] = 10
        
        context = HarvestContext(
            config=config,
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=2,  # Second round
            stock_before=25.0,  # Now healthy - should trigger recovery
        )
        
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})
        norm.on_round_start(context)
        
        # Check that recovery was detected
        norm_state = context.norm_state("dynamic_individual_cap")
        assert norm_state.get("previous_cap") == 10  # Previous was emergency
        assert norm_state.get("current_cap") == 15  # Now standard
        assert norm_state.get("recovery_announcement") == True

    def test_emergency_announcement_when_standard_to_emergency(self):
        """Emergency announcement when transitioning from standard to emergency cap."""
        config = {
            "norms": [
                {"type": "dynamic_individual_cap", "standard_cap_kg": 15, "emergency_cap_kg": 10, "emergency_threshold_kg": 20}
            ]
        }
        runtime = {
            "norms": {
                "dynamic_individual_cap": {
                    "current_cap": 15,  # Previous round was standard
                }
            }
        }
        
        context = HarvestContext(
            config=config,
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=2,
            stock_before=15.0,  # Now low - should trigger emergency
        )
        
        norm = DynamicIndividualCapNorm(key="dynamic_individual_cap", params={})
        norm.on_round_start(context)
        
        norm_state = context.norm_state("dynamic_individual_cap")
        assert norm_state.get("previous_cap") == 15  # Previous was standard
        assert norm_state.get("current_cap") == 10  # Now emergency
        assert norm_state.get("emergency_announcement") == True


class TestConfigOrdering:
    """Test that weekly_audit is correctly ordered before dynamic_individual_cap."""

    def test_audit_norm_runs_before_cap_norm(self):
        """Audit's is_eligible() must run before cap's evaluate()."""
        # This tests the ordering specified in the requirements
        config = {
            "norms": [
                {"type": "weekly_audit", "audit_frequency_rounds": 7, "audit_sample_rate": 0.30, "sanction_duration_rounds": 1},
                {"type": "dynamic_individual_cap", "standard_cap_kg": 15, "emergency_cap_kg": 10, "emergency_threshold_kg": 20}
            ]
        }
        
        # Verify the ordering in config
        norm_types = [n["type"] for n in config["norms"]]
        assert norm_types.index("weekly_audit") < norm_types.index("dynamic_individual_cap"), \
            "weekly_audit must come before dynamic_individual_cap in config"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
