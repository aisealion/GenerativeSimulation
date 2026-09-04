# Round 3 Norm Specification

## Source Text (from norm.txt)

**Policy:** Each fisher may take no more than 15 kg per trip; any catch beyond that must be returned to the lake immediately.

**Operationalization:** All fishers record their catch on a shared ledger each day. If a fisher exceeds 15 kg, the excess must be placed back into the lake or a communal tank by 8 pm that day. The community will conduct a random audit once a week; those who fail to return excess will lose fishing rights for one trip. If lake reserves fall below 20 kg, the maximum per trip is lowered to 10 kg until reserves recover.

---

## Clarifications & Ambiguities Resolved

**Q1: What is the difference between "returned to the lake" vs. "community pool" from Round 2?**
- **Resolution:** Round 2's "community pool" was a sink — fish were set aside for communal benefit but did NOT regenerate lake stock. Round 3's "returned to the lake" means fish go back into the lake's available stock and can be caught again in future rounds. This is a fundamental change: excess fish replenish the lake rather than being removed from circulation.

**Q2: What happens to fish "placed back into the lake or a communal tank"?**
- **Resolution:** Both "lake" and "communal tank" represent fish being returned to the available stock. For this implementation, "communal tank" is interpreted as a temporary holding that ultimately returns to the lake stock by end-of-day. The key distinction from Round 2 is that these fish regenerate available stock, they are not sequestered.

**Q3: How is "random audit once a week" interpreted in rounds?**
- **Resolution:** One week = 7 rounds. At the end of every 7th round (when round_number % 7 == 0), a random audit occurs. The audit randomly selects agents to check against the shared ledger. If an agent exceeded 15 kg in any audited round AND failed to return the excess (i.e., their kept amount exceeded the cap after norms were applied), they are flagged.

**Q4: What does "lose fishing rights for one trip" mean?**
- **Resolution:** The sanctioned agent is banned from fishing for exactly one round. This is implemented via `is_eligible()` returning False for that agent in the next round they would have participated. After one round of ban, eligibility is restored automatically.

**Q5: How is "failure to return excess" detected?**
- **Resolution:** The shared ledger records each agent's catch BEFORE any norm enforcement is applied (their "logged catch"). The audit compares this logged catch against what they were allowed to keep (after caps). If logged catch > 15 kg AND the agent did not return (logged catch - 15 kg) to the lake, they failed the audit. Since the norm enforces returns automatically, "failure" primarily means the norm system itself flagged a violation (attempted to keep excess).

**Q6: What does "lake reserves" mean exactly?**
- **Resolution:** Lake reserves = available fish stock at the START of the round (before any fishing occurs), as reported by `available_stock()` in the physics system. This is `stock_before` in the HarvestContext.

**Q7: When does the 10 kg dynamic cap apply?**
- **Resolution:** The 10 kg cap applies when `stock_before < 20 kg`. It replaces the normal 15 kg cap entirely until reserves recover to >= 20 kg. The check happens at round start; the cap applies to that entire round.

**Q8: What constitutes "reserves recover"?**
- **Resolution:** Reserves are considered recovered when `stock_before >= 20 kg` at the start of a round. Since returning excess to the lake regenerates stock, the dynamic cap creates a negative feedback loop that helps recovery.

**Q9: Does the dynamic cap apply to the collective limit or just individual?**
- **Resolution:** The operationalization states "maximum per trip is lowered to 10 kg" — this refers to the individual per-trip maximum. The collective daily limit from Round 2 (200 kg) is NOT mentioned in Round 3 and is therefore removed. Round 3 norms focus on individual caps only.

**Q10: Does the audit check historical rounds or only the current week?**
- **Resolution:** The audit checks the current completed week only (the most recent 7 rounds). Historical violations outside the audit window do not trigger sanctions, though they may be visible in the shared ledger.

---

## Requirements List

### R3.1 Individual Per-Trip Cap (Dynamic) [PRECISE]
Each fisher may keep at most:
- 15 kg per trip when lake reserves >= 20 kg at round start
- 10 kg per trip when lake reserves < 20 kg at round start
The cap is evaluated at round start and applies uniformly to all agents that round.

### R3.2 Excess Return to Lake [PRECISE]
If an agent's raw catch exceeds the applicable cap (15 or 10 kg), the excess must be returned to the lake immediately. This means:
- The agent keeps at most the cap amount
- The excess (raw catch - kept amount) is added back to the lake stock
- The return happens automatically as part of norm enforcement

### R3.3 Shared Ledger Logging [PRECISE]
Every agent's raw catch (before any norm enforcement) is recorded in a shared ledger visible to all. The ledger persists across rounds and tracks:
- Agent ID
- Round number
- Raw catch amount (before caps)
- Amount kept (after caps)
- Amount returned to lake

### R3.4 Weekly Random Audit [PRECISE]
At the end of every 7th round (round_number % 7 == 0), a random audit occurs:
- Randomly select 30% of agents (minimum 1) to audit
- For each audited agent, check all rounds in the current week (last 7 rounds)
- If in any audited round the agent's raw catch > applicable cap AND they kept > cap (i.e., failed to return excess), flag a violation

### R3.5 Fishing Rights Suspension [PRECISE]
Agents flagged in the audit lose fishing rights for exactly one trip (one round):
- `is_eligible()` returns False for the next round
- After one banned round, eligibility is automatically restored
- The ban is tracked via per-agent state with a countdown

### R3.6 Audit Transparency [PRECISE]
Agents are informed via the harvest prompt:
- Whether an audit occurred in the previous round
- Which agents (if any) were sanctioned
- That sanctioned agents are banned next round

### R3.7 Dynamic Cap Announcement [PRECISE]
When the 10 kg emergency cap is in effect (reserves < 20 kg), agents are informed:
- The emergency cap is active due to low reserves
- The current cap amount (10 kg)
- That the normal 15 kg cap will resume when reserves recover

### R3.8 Lake Stock Replenishment [PRECISE]
All excess fish returned due to the individual cap are added back to the lake stock immediately. This happens via `context.override_stock_after_regrowth()` in `on_round_end()`.

### R3.9 Audit History Visibility [PRECISE]
The shared ledger is public and visible to all agents. The `describe()` method includes:
- Recent ledger entries (last 3 rounds)
- Current week's audit status
- Any active sanctions

### R3.10 Recovery Detection [PRECISE]
At the start of each round, check if reserves have recovered:
- If previous round used 10 kg cap AND current reserves >= 20 kg: announce recovery
- If previous round used 15 kg cap AND current reserves < 20 kg: announce emergency cap
- Track which cap was used in the previous round for comparison

---

## Fluent Additions

| fluent name | visibility | description |
|-------------|------------|-------------|
| `audit_violation` | public | Records that an agent violated the return requirement in a specific round. Initiated when audit detects failure to return excess, terminated after sanction is applied. |
| `fishing_ban` | public | Indicates an agent is banned from fishing for the current round. Initiated at audit end, auto-terminates after one round. |

---

## New Norm Plugins Required

### `norms/dynamic_individual_cap.py`
Replaces the static individual cap with a dynamic one based on lake reserves.

**Type name:** `dynamic_individual_cap`

**Parameters:**
- `standard_cap_kg` (default: 15): Maximum per trip when reserves >= threshold
- `emergency_cap_kg` (default: 10): Maximum per trip when reserves < threshold
- `emergency_threshold_kg` (default: 20): Reserve level triggering emergency cap

**Hooks:**
- `describe()`: Inform agents of current cap (standard or emergency) and reason
- `evaluate()`: Apply the appropriate cap based on current reserves, record in ledger
- `on_round_start()`: Determine which cap applies this round, track cap history
- `on_round_end()`: Return excess to lake stock via stock override

**State:**
- `ledger`: List of {round, agent_id, raw_catch, kept, returned, cap_applied}
- `current_cap`: The cap used this round (for recovery detection)
- `previous_cap`: The cap used last round (for recovery detection)

### `norms/weekly_audit.py`
Implements weekly random audits and fishing rights suspension.

**Type name:** `weekly_audit`

**Parameters:**
- `audit_frequency_rounds` (default: 7): How often audits occur
- `audit_sample_rate` (default: 0.30): Fraction of agents to audit
- `sanction_duration_rounds` (default: 1): How many rounds to ban violators

**Hooks:**
- `describe()`: Inform agents of recent audit results and active bans
- `is_eligible()`: Return False for agents with active ban
- `on_round_end()`: If audit round, select random sample, check ledger for violations, apply bans

**State:**
- `pending_bans`: Dict of agent_id -> rounds remaining
- `last_audit_round`: Round number of most recent audit
- `audit_history`: List of audit results for transparency

---

## Config Changes

```json
{
  "norms": [
    {"type": "weekly_audit", "audit_frequency_rounds": 7, "audit_sample_rate": 0.30, "sanction_duration_rounds": 1},
    {"type": "dynamic_individual_cap", "standard_cap_kg": 15, "emergency_cap_kg": 10, "emergency_threshold_kg": 20}
  ]
}
```

**Ordering rationale:**
- `weekly_audit` must run BEFORE `dynamic_individual_cap` because:
  1. The audit's `is_eligible()` hook needs to run first to block banned agents
  2. Banned agents should not have their catch processed by the cap norm at all

**Note:** The `daily_collective_limit` and `deficit_penalty` norms from Round 2 are REMOVED as they are superseded by Round 3 norms.

---

## Test Cases

### TC-R3-1: Standard cap applies with healthy reserves
- Lake reserves = 50 kg (>= 20)
- Agent catches 20 kg
- Cap = 15 kg, kept = 15 kg, returned = 5 kg
- Lake stock after = 50 - 15 + 5 = 40 kg

### TC-R3-2: Emergency cap applies with low reserves
- Lake reserves = 15 kg (< 20)
- Agent catches 15 kg
- Cap = 10 kg, kept = 10 kg, returned = 5 kg
- Lake stock after = 15 - 10 + 5 = 10 kg

### TC-R3-3: Recovery to standard cap
- Round N: Reserves = 15 kg, emergency cap (10 kg) applied
- Excess returns boost stock
- Round N+1: Reserves = 25 kg (>= 20), standard cap (15 kg) resumes
- Agent catches 18 kg, keeps 15 kg

### TC-R3-4: Audit detection and sanction
- Rounds 1-7: Agents fish, ledger records catches
- Round 7: Audit occurs
- Agent X exceeded cap in round 3 and kept excess
- Agent X flagged, receives 1-round ban for round 8
- Round 8: Agent X `is_eligible()` returns False
- Round 9: Agent X eligibility restored

### TC-R3-5: No violation, no sanction
- Rounds 1-7: Agent Y always respects cap (or returns excess properly)
- Round 7: Audit occurs, Agent Y not flagged
- Round 8: Agent Y remains eligible

### TC-R3-6: Partial audit sample
- 10 agents, 30% sample rate = 3 agents audited
- Only audited agents checked for violations
- Non-audited agents not sanctioned even if they violated

### TC-R3-7: Ledger persistence and visibility
- Agent checks ledger in round 5
- Can see rounds 2, 3, 4 entries (last 3 rounds)
- Cannot see round 1 (too old)

### TC-R3-8: Multiple rounds of violations
- Agent Z violates in rounds 3, 4, and 5
- All violations caught in round 7 audit
- Only ONE sanction applied (1-round ban), not cumulative

---

## Dependencies

- Existing `engine/norms/base.py` (Norm base class, NormDecision)
- Existing `engine/norms/context.py` (norm_state for persistence, round_scratch for round-local)
- Existing `engine/norms/engine.py` (chaining, hook orchestration)
- Existing fluent system in `state/fluents.json`
- New fluents: `audit_violation`, `fishing_ban`
- Stock physics via `mechanisms/stock_check.py` and `context.stock_before`

---

## Notes on Round 2 vs Round 3 Changes

1. **Removed:** `daily_collective_limit` norm (no collective 200 kg limit)
2. **Removed:** `deficit_penalty` norm (no community pool deficits)
3. **Removed:** `community_pool_kg` fluent (fish go to lake, not pool)
4. **Added:** Dynamic individual cap based on reserves
5. **Added:** Weekly audit mechanism
6. **Added:** Fishing rights suspension (bans)
7. **Changed:** Excess fish regenerate lake stock instead of going to community pool
