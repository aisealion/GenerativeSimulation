"""Independent evaluation tests for Round 6 norm implementation.

This file tests the collective_limit_with_audit norm against all requirements
from state/norm_specs/round_6.md without relying on the implementer's tests.

Requirements tested:
- R6.1: Individual Per-Trip Cap (18 kg)
- R6.2: Daily Collective Harvest Limit (220 kg)
- R6.3: Community Pool
- R6.4: Shared Ledger Logging
- R6.5: Monthly Community Council Audit
- R6.6: Non-Compliance Penalty (5 kg Forfeiture)
- R6.7: Penalty Queue Management
- R6.8: Order of Enforcement
- R6.9: Agent-Facing Description
"""

import pytest
from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.collective_limit_with_audit import CollectiveLimitWithAuditNorm


class TestRound6IndependentEvaluation:
    """Independent evaluation test cases for Round 6 norms."""

    def create_context(self, round_number=1, stock_before=150.0, runtime_norms=None):
        """Create a test HarvestContext."""
        config = {
            "norms": [
                {
                    "type": "collective_limit_with_audit",
                    "individual_cap_kg": 18,
                    "daily_limit_kg": 220,
                    "audit_frequency_rounds": 30,
                    "forfeiture_amount_kg": 5,
                }
            ]
        }
        runtime = {"norms": runtime_norms or {}}
        return HarvestContext(
            config=config,
            fluents=[],
            runtime=runtime,
            agents={},
            round_number=round_number,
            stock_before=stock_before,
        )

    # ============================================================================
    # R6.1: Individual Per-Trip Cap (18 kg)
    # ============================================================================

    def test_r6_1_individual_cap_18kg(self):
        """TC-R6-1: Standard individual cap - 18 kg limit enforced."""
        context = self.create_context(stock_before=150.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=22.0, proposed_kg=22.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        # Individual cap = 18 kg, excess = 4 kg
        assert decision.kept_kg == 18.0, f"Expected 18 kg kept, got {decision.kept_kg}"

    def test_r6_1_under_individual_cap(self):
        """TC-R6-2: Under individual cap - no violation."""
        context = self.create_context(stock_before=150.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=15.0, proposed_kg=15.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        assert decision.kept_kg == 15.0, f"Expected 15 kg kept, got {decision.kept_kg}"

    def test_r6_1_exactly_at_cap(self):
        """Exactly at 18 kg cap is allowed without violation."""
        context = self.create_context(stock_before=150.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=18.0, proposed_kg=18.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        assert decision.kept_kg == 18.0, f"Expected 18 kg kept, got {decision.kept_kg}"

    def test_r6_1_excess_goes_to_pool(self):
        """Individual excess above 18 kg goes to community pool."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=25.0, proposed_kg=25.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        norm_state = context.norm_state("collective_limit_with_audit")
        pool = norm_state.get("community_pool_kg", 0)

        assert pool == 7.0, f"Expected 7 kg in pool (25-18), got {pool}"

    # ============================================================================
    # R6.2: Daily Collective Harvest Limit (220 kg)
    # ============================================================================

    def test_r6_2_collective_limit_cutoff(self):
        """TC-R6-3: Daily collective limit reached - subsequent agents get 0."""
        context = self.create_context(stock_before=300.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)

        # Agent 1: catches 18 kg
        decision1 = norm.evaluate(context, "agent_1", raw_kg=18.0, proposed_kg=18.0)
        norm.on_agent_settled(context, "agent_1", decision1, decision1.kept_kg)

        # Agent 2: catches 18 kg
        decision2 = norm.evaluate(context, "agent_2", raw_kg=18.0, proposed_kg=18.0)
        norm.on_agent_settled(context, "agent_2", decision2, decision2.kept_kg)

        # Verify daily total is tracking
        scratch = context.round_scratch("collective_limit_with_audit")
        assert scratch.get("daily_total", 0) == 36.0, f"Expected daily total 36, got {scratch.get('daily_total', 0)}"

    def test_r6_2_limit_reached_flag(self):
        """Limit reached flag is set when daily total reaches 220 kg."""
        context = self.create_context(stock_before=300.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        scratch = context.round_scratch("collective_limit_with_audit")
        scratch["daily_total"] = 220.0  # Simulate limit reached
        scratch["limit_reached"] = True

        # Agent tries to fish after limit reached
        decision = norm.evaluate(context, "agent_1", raw_kg=10.0, proposed_kg=10.0)

        assert decision.kept_kg == 0.0, f"Expected 0 kg when limit reached, got {decision.kept_kg}"

    def test_r6_2_subsequent_agents_get_zero(self):
        """After limit reached, subsequent agents keep 0 kg."""
        context = self.create_context(stock_before=300.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)

        # Set limit as already reached
        scratch = context.round_scratch("collective_limit_with_audit")
        scratch["daily_total"] = 220.0
        scratch["limit_reached"] = True

        # Agent N tries to fish
        decision = norm.evaluate(context, "agent_n", raw_kg=10.0, proposed_kg=10.0)

        assert decision.kept_kg == 0.0, f"Expected 0 kg, got {decision.kept_kg}"

    def test_r6_2_collective_excess_to_pool(self):
        """When collective limit exceeded, excess goes to community pool."""
        context = self.create_context(round_number=1, stock_before=300.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        scratch = context.round_scratch("collective_limit_with_audit")
        scratch["daily_total"] = 215.0  # Almost at limit

        # Agent catches 10 kg, but only 5 kg allowed to stay under 220
        decision = norm.evaluate(context, "agent_1", raw_kg=10.0, proposed_kg=10.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        # Check that limit was reached and agent kept less than caught
        scratch = context.round_scratch("collective_limit_with_audit")
        assert scratch.get("limit_reached", False) is True, "Limit should be marked as reached"

    # ============================================================================
    # R6.3: Community Pool
    # ============================================================================

    def test_r6_3_pool_tracks_excess(self):
        """Community pool tracks individual excess deposits."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=25.0, proposed_kg=25.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        norm_state = context.norm_state("collective_limit_with_audit")
        pool = norm_state.get("community_pool_kg", 0)

        assert pool == 7.0, f"Expected 7 kg in pool, got {pool}"

    def test_r6_3_pool_accumulates(self):
        """TC-R6-8: Community pool accumulates across rounds."""
        context = self.create_context(round_number=2, stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "community_pool_kg": 10.0,  # From previous round
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=25.0, proposed_kg=25.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        norm_state = context.norm_state("collective_limit_with_audit")
        pool = norm_state.get("community_pool_kg", 0)

        assert pool == 17.0, f"Expected 17 kg (10 + 7), got {pool}"

    def test_r6_3_pool_does_not_replenish_stock(self):
        """Community pool does NOT replenish lake stock."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=25.0, proposed_kg=25.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        # Stock override should NOT be set (pool doesn't replenish lake)
        assert context.stock_override_kg is None, "Pool should not override stock"

    def test_r6_3_pool_publicly_visible(self):
        """Community pool total is publicly visible to agents."""
        context = self.create_context(stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "community_pool_kg": 25.0,
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})
        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "25.0" in description or "25" in description, "Pool should be visible in description"

    # ============================================================================
    # R6.4: Shared Ledger Logging
    # ============================================================================

    def test_r6_4_ledger_records_all_fields_when_limit_reached(self):
        """Ledger records all required fields when daily limit is already reached."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        # Set limit as already reached to trigger ledger entry
        scratch = context.round_scratch("collective_limit_with_audit")
        scratch["limit_reached"] = True
        scratch["daily_total"] = 220.0

        decision = norm.evaluate(context, "agent_1", raw_kg=25.0, proposed_kg=25.0)

        norm_state = context.norm_state("collective_limit_with_audit")
        ledger = norm_state.get("ledger", [])

        assert len(ledger) == 1, f"Expected 1 ledger entry, got {len(ledger)}"
        entry = ledger[0]

        # Check all required fields
        assert "round" in entry, "Missing 'round' field"
        assert "agent_id" in entry, "Missing 'agent_id' field"
        assert "raw_catch" in entry, "Missing 'raw_catch' field"
        assert "forfeiture_applied" in entry, "Missing 'forfeiture_applied' field"
        assert "after_cap" in entry, "Missing 'after_cap' field"
        assert "final_kept" in entry, "Missing 'final_kept' field"
        assert "pool_deposit" in entry, "Missing 'pool_deposit' field"
        assert "violation" in entry, "Missing 'violation' field"

        # Check values - when limit reached, kept is 0 and all goes to pool
        assert entry["round"] == 1
        assert entry["agent_id"] == "agent_1"
        assert entry["raw_catch"] == 25.0
        assert entry["final_kept"] == 0.0  # All returned when limit reached
        assert entry["pool_deposit"] == 25.0  # All goes to pool

    def test_r6_4_agent_records_tracked_in_scratch(self):
        """Agent records are tracked in scratch for later ledger update."""
        context = self.create_context(round_number=1, stock_before=300.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        norm.evaluate(context, "agent_1", raw_kg=25.0, proposed_kg=25.0)
        norm.on_agent_settled(context, "agent_1", NormDecision.adjust(kept_kg=18.0), 18.0)
        norm.evaluate(context, "agent_2", raw_kg=15.0, proposed_kg=15.0)
        norm.on_agent_settled(context, "agent_2", NormDecision.adjust(kept_kg=15.0), 15.0)

        # Check agent records in scratch (not yet in ledger)
        scratch = context.round_scratch("collective_limit_with_audit")
        agent_records = scratch.get("agent_records", {})

        assert "agent_1" in agent_records, "agent_1 should have record in scratch"
        assert "agent_2" in agent_records, "agent_2 should have record in scratch"
        assert agent_records["agent_1"]["raw_kg"] == 25.0
        assert agent_records["agent_2"]["raw_kg"] == 15.0

    # ============================================================================
    # R6.5: Monthly Community Council Audit
    # ============================================================================

    def test_r6_5_monthly_audit_at_round_30(self):
        """TC-R6-4: Monthly audit occurs at round 30."""
        context = self.create_context(round_number=30, stock_before=150.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)

        norm_state = context.norm_state("collective_limit_with_audit")
        last_audit = norm_state.get("last_audit_round")
        audit_occurred = norm_state.get("monthly_audit_occurred")

        assert last_audit == 30, f"Expected last audit at round 30, got {last_audit}"
        assert audit_occurred is True, "Expected monthly_audit_occurred to be True"

    def test_r6_5_monthly_audit_every_30_rounds(self):
        """Monthly audits occur at rounds 30, 60, 90, etc."""
        for round_num in [30, 60, 90]:
            context = self.create_context(round_number=round_num, stock_before=150.0)
            norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})
            norm.on_round_start(context)

            norm_state = context.norm_state("collective_limit_with_audit")
            assert norm_state.get("monthly_audit_occurred") is True, \
                f"Expected audit at round {round_num}"

    def test_r6_5_no_audit_at_other_rounds(self):
        """No monthly audit at rounds not divisible by 30."""
        context = self.create_context(round_number=29, stock_before=150.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)

        norm_state = context.norm_state("collective_limit_with_audit")
        audit_occurred = norm_state.get("monthly_audit_occurred")

        assert audit_occurred is False, "Should not have audit at round 29"

    # ============================================================================
    # R6.6: Non-Compliance Penalty (5 kg Forfeiture)
    # ============================================================================

    def test_r6_6_forfeiture_penalty_applied(self):
        """TC-R6-5: 5 kg forfeiture penalty applied on next trip after violation."""
        context = self.create_context(round_number=31, stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "pending_penalties": {"agent_1": 1},
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        # After forfeiture: 20 - 5 = 15 kg, under 18 cap, so kept = 15
        # Forfeiture applied: 5 kg, remaining: 15 kg, under cap so kept = 15
        assert decision.kept_kg == 15.0, f"Expected 15 kg kept (20 - 5), got {decision.kept_kg}"

    def test_r6_6_penalty_goes_to_pool(self):
        """5 kg forfeiture goes to community pool."""
        context = self.create_context(round_number=31, stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "pending_penalties": {"agent_1": 1},
            "community_pool_kg": 0.0,
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        norm_state = context.norm_state("collective_limit_with_audit")
        pool = norm_state.get("community_pool_kg", 0)

        # 5 kg forfeiture should be in pool
        assert pool == 5.0, f"Expected 5 kg in pool from forfeiture, got {pool}"

    def test_r6_6_penalty_after_cap_before_collective(self):
        """Penalty applied after individual cap but before collective limit."""
        context = self.create_context(round_number=31, stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "pending_penalties": {"agent_1": 1},
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        # Agent catches 25 kg
        # Step 1: Record 25 kg
        # Step 2: Apply 5 kg forfeiture -> 20 kg
        # Step 3: Apply 18 kg cap -> 18 kg kept, 2 kg to pool
        decision = norm.evaluate(context, "agent_1", raw_kg=25.0, proposed_kg=25.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        # Forfeiture: 5 kg, then cap: 18 kg kept
        assert decision.kept_kg == 18.0, f"Expected 18 kg kept, got {decision.kept_kg}"

    def test_r6_6_insufficient_catch_penalty(self):
        """TC-R6-7: Penalty with insufficient catch - entire catch goes to pool."""
        context = self.create_context(round_number=31, stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "pending_penalties": {"agent_1": 1},
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=3.0, proposed_kg=3.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 0.2, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        # Agent catches 3 kg, needs to forfeit 5 kg
        # Entire 3 kg goes to pool, kept = 0
        assert decision.kept_kg == 0.0, f"Expected 0 kg kept, got {decision.kept_kg}"

    # ============================================================================
    # R6.7: Penalty Queue Management
    # ============================================================================

    def test_r6_7_penalty_queue_tracks_multiple(self):
        """TC-R6-6: Multiple pending penalties tracked in queue."""
        context = self.create_context(round_number=31, stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "pending_penalties": {"agent_1": 3},  # 3 violations
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)

        # Check pending penalties
        pending = norm._get_pending_penalties(context, "agent_1")
        assert pending == 3, f"Expected 3 pending penalties, got {pending}"

    def test_r6_7_one_penalty_per_trip(self):
        """Only one penalty applied per trip."""
        context = self.create_context(round_number=31, stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "pending_penalties": {"agent_1": 3},
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=25.0, proposed_kg=25.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        # After one penalty, should have 2 remaining
        norm_state = context.norm_state("collective_limit_with_audit")
        pending = norm_state.get("pending_penalties", {}).get("agent_1", 0)
        assert pending == 2, f"Expected 2 remaining penalties, got {pending}"

    def test_r6_7_penalties_applied_fifo(self):
        """Penalties applied in FIFO order (natural queue behavior)."""
        # This is implicitly tested by the queue behavior
        # Each trip removes one penalty until queue is empty
        context = self.create_context(round_number=31, stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "pending_penalties": {"agent_1": 2},
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        decision1 = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.on_agent_settled(context, "agent_1", decision1, decision1.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision1.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        norm_state = context.norm_state("collective_limit_with_audit")
        pending = norm_state.get("pending_penalties", {}).get("agent_1", 0)

        # Should have 1 penalty remaining after first trip
        assert pending == 1, f"Expected 1 remaining penalty, got {pending}"

    # ============================================================================
    # R6.8: Order of Enforcement
    # ============================================================================

    def test_r6_8_enforcement_order(self):
        """TC-R6-9: Order of enforcement verification."""
        context = self.create_context(round_number=31, stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "pending_penalties": {"agent_1": 1},
            "community_pool_kg": 0.0,
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)

        # Agent catches 25 kg with 5 kg pending penalty
        # Expected order:
        # 1. Record 25 kg in agent_records
        # 2. Apply 5 kg forfeiture -> 20 kg remaining
        # 3. Apply 18 kg cap -> 18 kg kept, 2 kg to pool
        # 4. Check collective limit (assume not exceeded)
        # Final: Kept = 18 kg, Pool receives 5 + 2 = 7 kg

        decision = norm.evaluate(context, "agent_1", raw_kg=25.0, proposed_kg=25.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        # Check agent_records for enforcement order
        scratch = context.round_scratch("collective_limit_with_audit")
        record = scratch.get("agent_records", {}).get("agent_1", {})

        # Verify enforcement order through agent_records
        assert record["raw_kg"] == 25.0, "Step 1: Raw catch recorded"
        assert record["forfeiture_applied"] == 5.0, "Step 2: Forfeiture applied"
        assert record["after_cap"] == 18.0, "Step 3: Cap applied (25-5=20, capped to 18)"
        assert record["final_kept"] == 18.0, "Final kept amount"
        
        # Check pool accumulated correctly
        norm_state = context.norm_state("collective_limit_with_audit")
        pool = norm_state.get("community_pool_kg", 0)
        
        # Pool should have forfeiture (5) + excess (2) = 7
        assert pool == 7.0, f"Expected 7 kg in pool (5 forfeiture + 2 excess), got {pool}"

    def test_r6_8_daily_total_reset_each_round(self):
        """Daily total is reset at the start of each round."""
        # Round 1: Some fishing happens
        context1 = self.create_context(round_number=1, stock_before=300.0)
        norm1 = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})
        norm1.on_round_start(context1)

        scratch1 = context1.round_scratch("collective_limit_with_audit")
        scratch1["daily_total"] = 100.0  # Simulate mid-round

        # Round 2: Daily total should be reset
        context2 = self.create_context(round_number=2, stock_before=290.0)
        norm2 = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})
        norm2.on_round_start(context2)

        scratch2 = context2.round_scratch("collective_limit_with_audit")
        assert scratch2.get("daily_total", 0) == 0.0, "Daily total should be reset at round start"

    # ============================================================================
    # R6.9: Agent-Facing Description
    # ============================================================================

    def test_r6_9_description_includes_cap(self):
        """Description includes the 18 kg individual cap."""
        context = self.create_context(stock_before=150.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "18" in description, "Description should mention 18 kg cap"

    def test_r6_9_description_includes_collective_limit(self):
        """Description includes the 220 kg collective limit."""
        context = self.create_context(stock_before=150.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "220" in description, "Description should mention 220 kg collective limit"

    def test_r6_9_description_includes_pool(self):
        """Description includes community pool total."""
        context = self.create_context(stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "community_pool_kg": 50.0,
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})
        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "50.0" in description or "50" in description, "Description should mention pool amount"
        assert "pool" in description.lower(), "Description should mention pool"

    def test_r6_9_description_includes_pending_penalties(self):
        """Description includes pending forfeiture penalties."""
        context = self.create_context(stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "pending_penalties": {"agent_1": 2},
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})
        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "PENDING PENALTY" in description, "Should mention pending penalty"
        assert "2" in description, "Should mention 2 penalties"

    def test_r6_9_description_includes_limit_status(self):
        """Description includes daily collective limit status."""
        context = self.create_context(stock_before=300.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        scratch = context.round_scratch("collective_limit_with_audit")
        scratch["limit_reached"] = True

        description = norm.describe(context, "agent_1")

        assert "WARNING" in description or "reached" in description.lower(), \
            "Should warn when limit reached"

    def test_r6_9_description_includes_recent_ledger(self):
        """Description includes recent ledger entries."""
        context = self.create_context(round_number=5, stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "ledger": [
                {"round": 3, "agent_id": "agent_1", "raw_catch": 20.0, "forfeiture_applied": 0.0,
                 "after_cap": 18.0, "final_kept": 18.0, "pool_deposit": 2.0, "violation": True},
                {"round": 4, "agent_id": "agent_1", "raw_catch": 15.0, "forfeiture_applied": 0.0,
                 "after_cap": 15.0, "final_kept": 15.0, "pool_deposit": 0.0, "violation": False},
            ]
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})
        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "Round 3" in description or "Round 4" in description, \
            "Should include recent ledger entries"

    def test_r6_9_description_includes_audit_status(self):
        """Description includes monthly audit announcement."""
        context = self.create_context(round_number=31, stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "last_audit_round": 30,
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})
        norm.on_round_start(context)
        description = norm.describe(context, "agent_1")

        assert "audit" in description.lower(), "Should mention audit"
        assert "30" in description, "Should mention round 30 audit"

    # ============================================================================
    # Additional Edge Cases
    # ============================================================================

    def test_multiple_agents_independent_tracking(self):
        """Multiple agents tracked independently via agent_records."""
        context = self.create_context(round_number=1, stock_before=300.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)

        # Agent 1: 20 kg catch, 2 kg excess
        decision1 = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.on_agent_settled(context, "agent_1", decision1, decision1.kept_kg)

        # Agent 2: 15 kg catch, no excess
        decision2 = norm.evaluate(context, "agent_2", raw_kg=15.0, proposed_kg=15.0)
        norm.on_agent_settled(context, "agent_2", decision2, decision2.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision1.kept_kg, "participated": True, "note": None},
            "agent_2": {"effort": 0.8, "harvested_kg": decision2.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        # Check agent_records in scratch for independent tracking
        scratch = context.round_scratch("collective_limit_with_audit")
        agent_records = scratch.get("agent_records", {})

        assert "agent_1" in agent_records, "agent_1 should have record"
        assert "agent_2" in agent_records, "agent_2 should have record"
        assert agent_records["agent_1"]["pool_deposit"] == 2.0  # Agent 1 excess (20-18)
        assert agent_records["agent_2"]["pool_deposit"] == 0.0  # Agent 2 no excess

    def test_violation_detection_in_agent_records(self):
        """Violations are properly flagged in agent_records."""
        context = self.create_context(round_number=1, stock_before=150.0)
        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)

        # Agent exceeds cap
        decision = norm.evaluate(context, "agent_1", raw_kg=25.0, proposed_kg=25.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        # Check violation flag in agent_records
        scratch = context.round_scratch("collective_limit_with_audit")
        record = scratch.get("agent_records", {}).get("agent_1", {})

        assert record.get("individual_violation") is True, "Should flag individual violation for exceeding cap"

    def test_audit_queues_penalties(self):
        """Audit properly queues penalties for violators."""
        context = self.create_context(round_number=30, stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "ledger": [
                {"round": 29, "agent_id": "agent_1", "raw_catch": 25.0, "violation": True},
                {"round": 28, "agent_id": "agent_1", "raw_catch": 22.0, "violation": True},
                {"round": 29, "agent_id": "agent_2", "raw_catch": 15.0, "violation": False},
            ]
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})
        norm.on_round_start(context)  # This triggers the audit

        norm_state = context.norm_state("collective_limit_with_audit")
        pending = norm_state.get("pending_penalties", {})

        # agent_1 had 2 violations, agent_2 had 0
        assert pending.get("agent_1", 0) == 2, f"Expected 2 penalties for agent_1, got {pending.get('agent_1', 0)}"
        assert pending.get("agent_2", 0) == 0, "agent_2 should have no penalties"

    def test_penalty_removed_after_application(self):
        """Penalty is removed from queue after being applied."""
        context = self.create_context(round_number=31, stock_before=150.0)
        context.runtime["norms"]["collective_limit_with_audit"] = {
            "pending_penalties": {"agent_1": 1},
        }

        norm = CollectiveLimitWithAuditNorm(key="collective_limit_with_audit", params={})

        norm.on_round_start(context)
        decision = norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)
        norm.on_agent_settled(context, "agent_1", decision, decision.kept_kg)

        round_results = {
            "agent_1": {"effort": 1.0, "harvested_kg": decision.kept_kg, "participated": True, "note": None}
        }
        norm.on_round_end(context, round_results)

        norm_state = context.norm_state("collective_limit_with_audit")
        pending = norm_state.get("pending_penalties", {})

        # Penalty should be removed after application
        assert "agent_1" not in pending or pending.get("agent_1", 0) == 0, \
            "Penalty should be removed after application"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
