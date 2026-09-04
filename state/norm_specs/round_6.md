# Round 6 Norm Specification

## Source Text (from norm.txt)

**Policy:** Each fisher may keep up to 18 kg per trip; the lake's total harvest per day cannot exceed 220 kg. Any excess from a fisher's haul or from the daily total is returned to a community pool.

**Operationalization:** At the end of each trip, every fisher records their haul on the shared ledger and deposits any surplus over 18 kg into the pool. If the combined daily harvest reaches 220 kg, any subsequent fish caught that day are automatically returned to the pool. The community council audits the ledger monthly; a fisher who fails to comply must forfeit 5 kg of their next trip's catch.

---

## Clarifications & Ambiguities Resolved

**Q1: What is the "community pool" vs "the lake"?**
- **Resolution:** The community pool is a separate reservoir from the lake stock. Fish deposited into the community pool do NOT replenish lake stock. The pool is managed by the community council for collective benefit. This is different from returning fish to the lake (which would replenish stock).

**Q2: What happens to excess from individual cap vs daily collective limit?**
- **Resolution:** Both types of excess go to the community pool:
  - Individual excess: If an agent catches >18 kg, the surplus (catch - 18 kg) goes to the pool
  - Collective excess: If total daily harvest exceeds 220 kg, proportional surplus from all agents goes to the pool
  - Agents keep the minimum of: (a) their individual cap, (b) their proportional share if collective limit exceeded

**Q3: What is "monthly" in terms of rounds?**
- **Resolution:** One month = 30 rounds. The community council audit occurs at the end of every 30th round (when round_number % 30 == 0). The audit reviews the shared ledger for violations.

**Q4: What constitutes "fails to comply"?**
- **Resolution:** A compliance failure occurs when:
  - An agent's raw catch exceeds 18 kg (individual cap violation)
  - An agent fishes after the daily collective limit of 220 kg has been reached
  - An agent attempts to avoid the shared ledger recording requirement
  Non-compliance is recorded in the ledger at the time of the violation.

**Q5: How does the 5 kg forfeiture penalty work?**
- **Resolution:** When an agent is flagged as non-compliant during a monthly audit:
  - The violation is recorded in their compliance history
  - On their very next trip (the immediate next round they fish), exactly 5 kg is deducted from their kept catch
  - This 5 kg goes to the community pool
  - The deduction is applied AFTER the individual 18 kg cap but BEFORE the collective 220 kg limit calculation
  - If the agent catches less than 5 kg, their entire catch goes to the pool and they keep 0 kg

**Q6: Can an agent have multiple pending penalties?**
- **Resolution:** Yes. If an agent violates norms multiple times between audits, they accrue multiple 5 kg penalties. Each penalty is applied on consecutive trips:
  - Trip 1: Apply first 5 kg penalty
  - Trip 2: Apply second 5 kg penalty (if another violation was recorded)
  - And so on...
  Penalties are tracked in a queue (FIFO order) in the agent's state.

**Q7: What is the order of enforcement?**
- **Resolution:** The order is:
  1. Record raw catch in shared ledger
  2. Apply any pending 5 kg forfeiture penalties from previous non-compliance
  3. Apply individual 18 kg cap (excess to pool)
  4. Check collective 220 kg limit (if exceeded, proportional surplus to pool)
  5. Final kept amount is the minimum after all adjustments

**Q8: How is the shared ledger different from previous rounds?**
- **Resolution:** The shared ledger records:
  - Agent ID
  - Round number
  - Raw catch amount
  - Amount after penalties
  - Amount after individual cap
  - Amount after collective adjustment
  - Final kept amount
  - Total deposited to community pool
  - Violation flags

**Q9: What happens when the 220 kg daily limit is reached?**
- **Resolution:** The operationalization says "any subsequent fish caught that day are automatically returned to the pool." This means:
  - The limit is checked after each agent's catch
  - Once cumulative total reaches or exceeds 220 kg, subsequent agents that round get 0 kg
  - Their entire catch goes to the community pool
  - This is different from proportional redistribution—it's a hard cutoff

**Q10: Does Round 6 replace or add to Round 5 norms?**
- **Resolution:** Round 6 represents a new policy regime that replaces Round 5 norms. The Round 5 norm (`sustenance_cap_with_obligation`) is removed. The community pool from Round 5 persists, but individual obligations and penalties are cleared. All agents start fresh under the new 18 kg / 220 kg system.

---

## Requirements List

### R6.1 Individual Per-Trip Cap (18 kg) [PRECISE]
Each fisher may keep at most 18 kg per trip. This is a fixed cap applied uniformly to all agents every round. Any excess above 18 kg is deposited into the community pool.

### R6.2 Daily Collective Harvest Limit (220 kg) [PRECISE]
The lake's total daily harvest cannot exceed 220 kg. Once the cumulative total reaches 220 kg:
- Subsequent agents that round receive 0 kg (entire catch goes to pool)
- The cutoff is applied immediately when the limit is reached
- The limit is checked after each agent's catch is finalized

### R6.3 Community Pool [PRECISE]
A community pool tracks all surplus and penalty deposits:
- Receives individual cap excess (catch - 18 kg)
- Receives collective limit excess (proportional or cutoff-based)
- Receives 5 kg forfeiture penalties from non-compliant agents
- Does NOT replenish lake stock
- Persistent across rounds
- Publicly visible to all agents

### R6.4 Shared Ledger Logging [PRECISE]
Every agent's catch details are recorded in a shared ledger:
- Agent ID
- Round number
- Raw catch amount
- Forfeiture penalties applied (if any)
- Amount after individual cap
- Amount after collective adjustment
- Final kept amount
- Total deposited to community pool
- Violation flags (individual cap violation, collective limit violation)

### R6.5 Monthly Community Council Audit [PRECISE]
At the end of every 30th round (round_number % 30 == 0):
- A formal audit of the shared ledger occurs
- All violations from the past month are assessed
- Agents with violations are flagged for 5 kg forfeiture penalties
- Penalties are queued for application on the agent's next trip
- Audit results are announced to all agents

### R6.6 Non-Compliance Penalty (5 kg Forfeiture) [PRECISE]
Agents flagged during monthly audit for violations must forfeit 5 kg on their next trip:
- 5 kg is deducted from their kept amount
- The deducted 5 kg goes to the community pool
- Applied after individual cap but before collective limit
- If agent catches less than 5 kg, entire catch goes to pool (kept = 0)
- Multiple penalties can be queued and applied on consecutive trips

### R6.7 Penalty Queue Management [PRECISE]
Penalties are tracked per-agent in a queue:
- New penalties are added to the queue during monthly audit
- One penalty is applied per trip (the oldest pending penalty)
- After application, the penalty is removed from the queue
- Queue persists across rounds until all penalties are cleared

### R6.8 Order of Enforcement [PRECISE]
The enforcement order for each agent's catch is:
1. Record raw catch in ledger
2. Apply pending 5 kg forfeiture penalty (if any) from queue
3. Apply individual 18 kg cap (excess to pool)
4. Check collective 220 kg limit (cutoff if exceeded)
5. Finalize kept amount and update community pool

### R6.9 Agent-Facing Description [PRECISE]
Agents are informed via the harvest prompt:
- The 18 kg per-trip individual cap
- The 220 kg daily collective limit
- Current community pool total
- Any pending 5 kg forfeiture penalties
- Recent ledger entries (last 3 rounds)
- Whether a monthly audit occurred in the previous round
- Whether the daily collective limit has been reached

---

## Fluent Additions

| fluent name | visibility | description |
|-------------|------------|-------------|
| `community_pool_kg` | public | Cumulative total of the community pool. Increases from individual excess, collective surplus, and forfeiture penalties. |
| `pending_penalties` | private | Per-agent queue of pending 5 kg forfeiture penalties. Each entry represents one penalty to be applied on the next trip. |
| `monthly_audit` | public | Records that a monthly community council audit occurred in a specific round. Initiated at end of every 30th round. |
| `daily_total` | public | Tracks cumulative daily harvest total for collective limit enforcement. Reset each round. |

---

## New Norm Plugins Required

### `norms/collective_limit_with_audit.py`
Implements the 18 kg individual cap, 220 kg daily collective limit, monthly audits, and 5 kg forfeiture penalties.

**Type name:** `collective_limit_with_audit`

**Parameters:**
- `individual_cap_kg` (default: 18): Maximum per trip for each agent
- `daily_limit_kg` (default: 220): Maximum daily collective harvest
- `audit_frequency_rounds` (default: 30): How often monthly audits occur
- `forfeiture_amount_kg` (default: 5): Amount forfeited per violation

**Hooks:**
- `describe()`: Inform agents of caps, pool total, pending penalties, and audit status
- `on_round_start()`: Reset daily total, check for monthly audit
- `evaluate()`: Apply forfeiture penalty, individual cap, track in ledger
- `on_agent_settled()`: Check collective limit, apply cutoff if exceeded
- `on_round_end()`: Update community pool, process audit if needed, queue penalties

**State:**
- `ledger`: List of {round, agent_id, raw_catch, forfeiture_applied, after_cap, after_collective, final_kept, pool_deposit, violations}
- `community_pool_kg`: Cumulative pool total
- `pending_penalties`: Dict of agent_id -> list of pending penalty counts
- `daily_total`: Cumulative total for current round
- `limit_reached`: Boolean flag if 220 kg limit has been reached
- `last_audit_round`: Round number of most recent audit

---

## Config Changes

```json
{
  "norms": [
    {"type": "collective_limit_with_audit", "individual_cap_kg": 18, "daily_limit_kg": 220, "audit_frequency_rounds": 30, "forfeiture_amount_kg": 5}
  ]
}
```

**Ordering rationale:**
- This single norm replaces the Round 5 norm. It handles individual cap, collective limit, monthly audits, and penalties in one integrated plugin.

**Note:** Round 5's `sustenance_cap_with_obligation` norm is REMOVED as it is superseded by Round 6's approach. The community pool amount from Round 5 persists, but individual obligations are cleared.

---

## Test Cases

### TC-R6-1: Standard individual cap
- Agent catches 22 kg
- Individual cap = 18 kg, pool deposit = 4 kg
- Daily total = 18 kg
- Kept = 18 kg

### TC-R6-2: Under individual cap
- Agent catches 15 kg
- No individual cap violation (15 < 18)
- Pool deposit = 0 kg
- Kept = 15 kg

### TC-R6-3: Daily collective limit reached
- Agent A catches 18 kg (daily total = 18 kg)
- Agent B catches 18 kg (daily total = 36 kg)
- ... (many agents fish, daily total reaches 220 kg)
- Agent N catches 10 kg
- Since limit already reached, Agent N keeps 0 kg, 10 kg to pool

### TC-R6-4: Monthly audit at round 30
- Rounds 1-30: Agents fish, violations recorded
- Round 30: Monthly audit occurs
- Agents with violations flagged for 5 kg forfeiture
- Penalties queued for next trips

### TC-R6-5: Forfeiture penalty application
- Round 30: Agent X flagged for violation during audit
- Round 31: Agent X catches 20 kg
  - Forfeiture: 5 kg deducted, goes to pool
  - Remaining: 15 kg, under individual cap
  - Kept = 15 kg
  - Penalty cleared from queue

### TC-R6-6: Multiple pending penalties
- Round 30: Agent Y has 3 violations flagged
- Round 31: Agent Y catches 25 kg
  - Forfeiture: 5 kg deducted (1 of 3 penalties)
  - Remaining: 20 kg, capped to 18 kg, 2 kg to pool
  - Kept = 18 kg
  - 2 penalties remain in queue
- Round 32: Agent Y catches 20 kg
  - Forfeiture: 5 kg deducted (2 of 3 penalties)
  - Remaining: 15 kg, under cap
  - Kept = 15 kg
  - 1 penalty remains in queue

### TC-R6-7: Penalty with insufficient catch
- Round 30: Agent Z flagged for violation
- Round 31: Agent Z catches 3 kg
  - Forfeiture: 5 kg required but only 3 kg available
  - Entire 3 kg goes to pool
  - Kept = 0 kg
  - Remaining 2 kg penalty forgiven (cannot go negative)

### TC-R6-8: Community pool accumulation
- Round 1: 3 agents deposit excess, pool = X kg
- Round 2: 1 agent pays forfeiture, pool = X + 5 kg
- Round 3: Collective limit exceeded, surplus added, pool = X + 5 + Y kg
- Pool persists and accumulates across rounds

### TC-R6-9: Order of enforcement verification
- Agent has pending 5 kg penalty
- Agent catches 25 kg
- Step 1: Record 25 kg in ledger
- Step 2: Apply 5 kg forfeiture → 20 kg remaining
- Step 3: Apply 18 kg cap → 18 kg kept, 2 kg to pool
- Step 4: Check collective limit (assume not exceeded)
- Final: Kept = 18 kg, Pool receives 5 + 2 = 7 kg

### TC-R6-10: Round 5 to Round 6 transition
- Round 5 end: Agent has communal obligation (3 kg)
- Round 6 start: Obligations cleared, all agents start fresh
- New 18 kg cap and 220 kg daily limit apply
- Round 5 community pool total persists

---

## Dependencies

- Existing `engine/norms/base.py` (Norm base class, NormDecision)
- Existing `engine/norms/context.py` (norm_state for persistence, round_scratch for round-local)
- Existing `engine/norms/engine.py` (chaining, hook orchestration)
- Existing fluent system in `state/fluents.json`
- New fluents: `community_pool_kg`, `pending_penalties`, `monthly_audit`, `daily_total`
- Stock physics via `mechanisms/stock_check.py` and `context.stock_before`

---

## Notes on Round 5 vs Round 6 Changes

1. **Changed:** Individual cap increased from 12 kg to 18 kg
2. **Changed:** Removed 1 kg self-sustenance minimum floor
3. **Removed:** Communal obligations and two-trip satisfaction window
4. **Removed:** Weekly reviews (7 rounds)
5. **Added:** Daily collective limit of 220 kg with hard cutoff
6. **Added:** Monthly audits (30 rounds) instead of weekly
7. **Added:** 5 kg forfeiture penalty for non-compliance
8. **Changed:** All excess goes to community pool (not lake)
9. **Changed:** Penalty queue system instead of obligation tracking
10. **Kept:** Shared ledger for transparency (enhanced with more fields)
