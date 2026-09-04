# Round 4 Norm Specification

## Source Text (from norm.txt)

**Policy:** Each fisher may take no more than 15 kg of fish per trip; any catch beyond that must be returned to the lake immediately, and each fisher must keep at least 1 kg for self sustenance.

**Operationalization:** Every fisher records their catch in a shared logbook. If a fisher's haul exceeds 15 kg, the excess is immediately returned to the lake and the fisher must pay a penalty of 1 kg to a communal pool. The community meets monthly to review lake stock, and if the stock falls below 100 kg, the limit automatically drops to 10 kg until stock recovers. Violations are penalized by reducing the next trip's limit by 5 kg.

---

## Clarifications & Ambiguities Resolved

**Q1: What is the difference between the "communal pool" in Round 4 and previous rounds?**
- **Resolution:** Round 4's "communal pool" is a penalty sink — when a fisher violates the 15 kg cap, they pay 1 kg as a penalty. This 1 kg goes to the communal pool and is NOT returned to the lake. Unlike Round 2's community pool (which collected proportional surplus), this pool only receives the 1 kg flat penalty per violation. The pool accumulates across rounds and does not regenerate lake stock.

**Q2: What constitutes a "violation" that triggers the 1 kg penalty?**
- **Resolution:** A violation occurs when an agent's raw catch exceeds the applicable cap (15 kg or 10 kg emergency cap). The penalty is applied automatically regardless of intent. Even if the excess is returned to the lake, the 1 kg penalty is still assessed for attempting to exceed the cap.

**Q3: How is "monthly" interpreted in rounds?**
- **Resolution:** One month = 30 rounds. The community stock review occurs at the end of every 30th round (when round_number % 30 == 0). The dynamic cap check (stock < 100 kg) happens at round start, but the formal "review meeting" is noted at the monthly interval.

**Q4: What does "reducing the next trip's limit by 5 kg" mean exactly?**
- **Resolution:** This is a per-agent escalating penalty. When an agent violates the cap:
  - Their next trip's individual limit is reduced by 5 kg below the standard cap
  - If standard cap is 15 kg, their personal limit becomes 10 kg for the next trip
  - If they violate again while under reduced limit, next trip reduces further (10 kg → 5 kg)
  - The minimum personal limit is 1 kg (the self-sustenance floor)
  - After a trip where they do NOT violate, their limit resets to the standard cap

**Q5: How does the self-sustenance minimum (1 kg) interact with penalties?**
- **Resolution:** The 1 kg minimum is a hard floor. Even if penalties would reduce an agent's keep below 1 kg, they must keep at least 1 kg. This means:
  - If cap - penalties < 1 kg, agent still keeps 1 kg
  - The floor applies after all cap and penalty calculations
  - If an agent catches less than 1 kg, they keep what they caught (can't create fish)

**Q6: What is the order of operations for norm enforcement?**
- **Resolution:** 
  1. Check eligibility (bans from previous violations)
  2. Apply deficit/penalty reductions from previous rounds
  3. Apply dynamic individual cap (15 kg or 10 kg based on stock)
  4. Apply personal violation penalty (reduced limit if applicable)
  5. Assess 1 kg communal pool penalty if violation occurred
  6. Return excess to lake
  7. Ensure minimum 1 kg floor
  8. Record in shared logbook

**Q7: What happens to the communal pool accumulation?**
- **Resolution:** The communal pool is tracked as a persistent state variable. It accumulates 1 kg per violation. The pool can be used for community benefit but does not affect lake regeneration. Unlike Round 2, there is no "deficit" concept — the 1 kg penalty is always paid from the agent's kept amount.

**Q8: How does the shared logbook differ from Round 3's ledger?**
- **Resolution:** The logbook serves the same function as Round 3's ledger — it records raw catch, kept amount, returned amount, and any penalties applied. The key addition is tracking violation penalties and personal limit reductions per agent.

**Q9: What triggers the dynamic cap reduction to 10 kg?**
- **Resolution:** At the start of each round, if `stock_before < 100 kg`, the cap for that round is 10 kg instead of 15 kg. This applies to all agents uniformly for that round. The cap returns to 15 kg when `stock_before >= 100 kg`.

**Q10: Can an agent have multiple pending penalties?**
- **Resolution:** No, the penalty system tracks one "next trip limit reduction" at a time. If an agent violates while already having a pending penalty, the penalties do not stack — instead, the new violation resets the penalty to "next trip limit - 5 kg" (calculated from the current standard cap). The agent must complete one compliant trip to clear the penalty.

---

## Requirements List

### R4.1 Individual Per-Trip Cap (Dynamic) [PRECISE]
Each fisher may keep at most:
- 15 kg per trip when lake stock >= 100 kg at round start
- 10 kg per trip when lake stock < 100 kg at round start
The cap is evaluated at round start and applies uniformly to all agents that round.

### R4.2 Self-Sustenance Minimum Floor [PRECISE]
Each fisher must keep at least 1 kg per trip for self-sustenance. This is a hard floor applied after all cap and penalty calculations. If the calculated keep amount is < 1 kg, the agent keeps 1 kg (unless they caught less than 1 kg total, in which case they keep their actual catch).

### R4.3 Violation Detection and 1 kg Penalty [PRECISE]
If an agent's raw catch exceeds the applicable cap:
- The excess (raw catch - cap) is returned to the lake immediately
- A 1 kg penalty is assessed and added to the communal pool
- The penalty is subtracted from the agent's kept amount (after cap, before floor)
- A violation flag is recorded for this agent

### R4.4 Personal Limit Reduction Penalty [PRECISE]
Agents who violate the cap receive a personal limit reduction for their next trip:
- Next trip's personal limit = standard cap - 5 kg
- This is tracked per-agent and applies only to that agent
- If they violate again while under reduced limit, the penalty resets (not stacks)
- After one compliant trip, the penalty clears and limit resets to standard
- The personal limit cannot go below the 1 kg floor

### R4.5 Shared Logbook [PRECISE]
Every agent's raw catch and norm enforcement details are recorded in a shared logbook:
- Agent ID
- Round number
- Raw catch amount
- Standard cap applicable that round
- Personal limit applied (if under penalty)
- Amount kept after all adjustments
- Amount returned to lake
- Penalty assessed (0 or 1 kg)
- Violation flag (true/false)

### R4.6 Communal Pool Tracking [PRECISE]
A communal pool tracks cumulative penalties across all rounds:
- Increases by 1 kg per violation
- Persistent across rounds
- Publicly visible to all agents
- Does NOT regenerate lake stock

### R4.7 Monthly Stock Review [PRECISE]
Every 30 rounds (round_number % 30 == 0), a formal stock review occurs:
- Current stock level is assessed
- If stock < 100 kg, emergency cap (10 kg) continues
- If stock >= 100 kg, standard cap (15 kg) resumes
- Review results are announced to all agents

### R4.8 Excess Return to Lake [PRECISE]
All excess fish (raw catch above applicable cap) are returned to the lake stock immediately. This happens via `context.override_stock_after_regrowth()` in `on_round_end()`.

### R4.9 Penalty Application Order [PRECISE]
For agents with pending personal limit reductions:
- The reduced limit applies INSTEAD of the standard cap
- Violation is assessed against the reduced limit
- If violated, standard 1 kg penalty applies
- After the trip (regardless of violation), the penalty clears

### R4.10 Agent-Facing Description [PRECISE]
Agents are informed via the harvest prompt:
- Current standard cap (15 kg or 10 kg emergency)
- Their personal limit if under penalty
- Current communal pool total
- The 1 kg self-sustenance floor
- Recent logbook entries (last 3 rounds)

---

## Fluent Additions

| fluent name | visibility | description |
|-------------|------------|-------------|
| `communal_pool_kg` | public | Cumulative total of 1 kg penalties paid to communal pool. Increments by 1 kg per violation. |
| `personal_limit_penalty` | private | Per-agent flag indicating they have a pending -5 kg limit reduction for next trip. |
| `violation_record` | private | Per-agent record of violations for tracking repeat offenses. |

---

## New Norm Plugins Required

### `norms/dynamic_cap_with_penalty.py`
Replaces the dynamic individual cap with enhanced penalty system and minimum floor.

**Type name:** `dynamic_cap_with_penalty`

**Parameters:**
- `standard_cap_kg` (default: 15): Maximum per trip when stock >= threshold
- `emergency_cap_kg` (default: 10): Maximum per trip when stock < threshold
- `emergency_threshold_kg` (default: 100): Stock level triggering emergency cap
- `min_keep_kg` (default: 1): Minimum self-sustenance floor
- `violation_penalty_kg` (default: 1): Amount paid to communal pool per violation
- `limit_reduction_kg` (default: 5): Amount to reduce next trip's limit on violation

**Hooks:**
- `describe()`: Inform agents of current cap, personal penalties, communal pool, and logbook
- `on_round_start()`: Determine which cap applies this round
- `evaluate()`: Apply personal limit reduction if pending, apply cap, assess violation penalty, ensure minimum floor, record in logbook
- `on_agent_settled()`: If violation occurred, set personal limit reduction for next trip
- `on_round_end()`: Return excess to lake, update communal pool total

**State:**
- `logbook`: List of {round, agent_id, raw_catch, standard_cap, personal_limit, kept, returned, penalty, violated}
- `communal_pool_kg`: Cumulative penalty total
- `personal_limits`: Dict of agent_id -> {reduced_limit, expires_after_round}
- `current_cap`: The standard cap used this round

---

## Config Changes

```json
{
  "norms": [
    {"type": "dynamic_cap_with_penalty", "standard_cap_kg": 15, "emergency_cap_kg": 10, "emergency_threshold_kg": 100, "min_keep_kg": 1, "violation_penalty_kg": 1, "limit_reduction_kg": 5}
  ]
}
```

**Ordering rationale:**
- This single norm replaces the Round 3 norm combination. It handles caps, penalties, minimum floor, and communal pool in one integrated plugin.

**Note:** Round 3's `weekly_audit` and `dynamic_individual_cap` norms are REMOVED as they are superseded by Round 4's integrated approach.

---

## Test Cases

### TC-R4-1: Standard cap applies with healthy stock
- Lake stock = 150 kg (>= 100)
- Agent catches 20 kg
- Cap = 15 kg, kept = 15 kg, returned = 5 kg
- Violation = true, penalty = 1 kg to pool
- Final kept = 14 kg (after 1 kg penalty)
- Lake stock after = 150 - 14 + 5 = 141 kg
- Communal pool = 1 kg

### TC-R4-2: Emergency cap applies with low stock
- Lake stock = 80 kg (< 100)
- Agent catches 15 kg
- Cap = 10 kg, kept = 10 kg, returned = 5 kg
- Violation = true, penalty = 1 kg to pool
- Final kept = 9 kg (after 1 kg penalty)
- Lake stock after = 80 - 9 + 5 = 76 kg

### TC-R4-3: Self-sustenance floor enforced
- Lake stock = 150 kg
- Agent has pending penalty (personal limit = 10 kg)
- Agent catches 10 kg
- Personal limit = 10 kg, no violation
- But let's say agent catches 8 kg with personal limit of 10 kg
- No violation, kept = 8 kg (above 1 kg floor, no penalty)

### TC-R4-4: Minimum floor below 1 kg
- Lake stock = 150 kg
- Agent has pending penalty (personal limit = 10 kg)
- Agent catches 11 kg
- Personal limit exceeded, violation = true
- Cap would give 10 kg, minus 1 kg penalty = 9 kg
- Floor not triggered (9 kg > 1 kg)
- But if: Agent catches 2 kg with personal limit of 10 kg
- No violation, kept = 2 kg (no penalty, above floor)

### TC-R4-5: Personal limit reduction applied
- Round 1: Agent catches 20 kg, violates 15 kg cap
- Returns 5 kg to lake, pays 1 kg penalty
- Kept = 14 kg, personal limit set to 10 kg for round 2
- Round 2: Agent's personal limit = 10 kg (instead of 15 kg)
- If catches 12 kg: violation against personal limit, another 1 kg penalty
- Returns 2 kg, pays 1 kg penalty, kept = 9 kg

### TC-R4-6: Penalty clears after compliant trip
- Round 1: Agent violates, gets personal limit = 10 kg for round 2
- Round 2: Agent catches 8 kg (under 10 kg limit), no violation
- Penalty clears, round 3 limit returns to 15 kg (or 10 kg emergency)

### TC-R4-7: Monthly review at round 30
- Rounds 1-29: Stock stays above 100 kg, standard cap (15 kg)
- Round 30: Monthly review occurs, stock still >= 100 kg
- Cap remains 15 kg, agents informed of review

### TC-R4-8: Emergency cap recovery
- Round 1: Stock = 80 kg, emergency cap (10 kg) applied
- Agents return excess, stock regenerates
- Round 2: Stock = 110 kg (>= 100), standard cap (15 kg) resumes
- Agents informed of recovery

### TC-R4-9: Communal pool accumulation
- Round 1: 3 agents violate, pool = 3 kg
- Round 2: 2 agents violate, pool = 5 kg
- Round 3: No violations, pool = 5 kg
- Pool persists and accumulates across rounds

### TC-R4-10: Multiple agents, different penalties
- Agent A: No penalty, standard cap (15 kg)
- Agent B: Pending penalty, personal limit (10 kg)
- Agent C: Pending penalty, personal limit (10 kg)
- Each evaluated against their own limit
- Violations tracked independently

### TC-R4-11: Hard floor at 1 kg
- Agent has personal limit of 10 kg
- Agent catches 11 kg, violates
- Kept after cap = 10 kg, minus 1 kg penalty = 9 kg
- If scenario: Agent has personal limit of 5 kg (from repeated violations)
- Agent catches 6 kg, violates
- Kept after cap = 5 kg, minus 1 kg penalty = 4 kg
- Floor (1 kg) is respected (4 kg > 1 kg)
- If personal limit somehow at 1 kg: catches 2 kg
- Kept after cap = 1 kg, minus 1 kg penalty = 0 kg, BUT floor raises to 1 kg
- Communal pool still gets 1 kg (from penalty)

---

## Dependencies

- Existing `engine/norms/base.py` (Norm base class, NormDecision)
- Existing `engine/norms/context.py` (norm_state for persistence, round_scratch for round-local)
- Existing `engine/norms/engine.py` (chaining, hook orchestration)
- Existing fluent system in `state/fluents.json`
- New fluents: `communal_pool_kg`, `personal_limit_penalty`, `violation_record`
- Stock physics via `mechanisms/stock_check.py` and `context.stock_before`

---

## Notes on Round 3 vs Round 4 Changes

1. **Removed:** `weekly_audit` norm (no random audits)
2. **Removed:** `dynamic_individual_cap` norm (replaced by integrated version)
3. **Added:** Minimum 1 kg self-sustenance floor
4. **Added:** 1 kg penalty to communal pool on every violation
5. **Added:** Personal limit reduction (-5 kg) for next trip on violation
6. **Changed:** Emergency threshold from 20 kg to 100 kg stock level
7. **Changed:** Monthly review (30 rounds) instead of weekly (7 rounds)
8. **Changed:** Communal pool receives flat 1 kg penalties instead of proportional surplus
9. **Added:** Escalating personal penalties that reset after compliant behavior
