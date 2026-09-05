# Round 7 Norm Specification

## Source Text (from norm.txt)

**Policy:** Each fisher may keep up to 20 kg per trip, and the lake's total harvest per day cannot exceed 260 kg. Any catch beyond a fisher's 20 kg limit or beyond the 260 kg daily total is returned to a community pool for shared use.

**Operationalization:** Every trip the fisher records their haul on a shared board; the community tallies daily catches. If a fisher's haul exceeds 20 kg, the excess is automatically placed into the pool. If the cumulative daily catch exceeds 260 kg, the last fisher to push the total over the limit must return the excess to the pool. Violations result in a brief fishing ban until the pool balance is restored and a community meeting is held to review the case.

---

## Changes from Round 6

| Aspect | Round 6 | Round 7 |
|--------|---------|---------|
| Individual cap | 18 kg | 20 kg |
| Daily collective limit | 220 kg | 260 kg |
| Collective limit enforcement | Hard cutoff for subsequent agents | Last fisher returns excess |
| Penalty | 5 kg forfeiture on next trip | Brief fishing ban + community meeting |

---

## Clarifications & Ambiguities Resolved

**Q1: What is the "brief fishing ban"?**
- **Resolution:** A fishing ban prevents the agent from fishing in the next round. The agent's "participated" flag is set to false, and they cannot submit a harvest decision. The ban is lifted after one round.

**Q2: What triggers the fishing ban?**
- **Resolution:** The fishing ban is triggered when:
  - An agent's raw catch exceeds 20 kg (individual cap violation)
  - An agent's catch pushes the cumulative daily total over 260 kg (collective limit violation)
  - The agent is identified as the one who caused the collective limit to be exceeded

**Q3: What is "the last fisher to push the total over the limit"?**
- **Resolution:** When an agent's kept amount (after individual cap) would cause the cumulative daily total to exceed 260 kg:
  - That specific agent is identified as the one who "pushed the total over"
  - They must return their entire catch to the pool (not just the excess)
  - Unlike Round 6's hard cutoff for subsequent agents, this only affects the specific agent who exceeded the limit

**Q4: What is the "pool balance restored" condition?**
- **Resolution:** The pool balance is considered "restored" when the community pool contains at least 10 kg. This provides a simple, objective criterion for ending the fishing ban.

**Q5: How does the community meeting work?**
- **Resolution:** A community meeting is a notification that appears in the agent's description in the round following a violation. It serves as a warning and reminder of the violation.

**Q6: What happens when an agent is banned?**
- **Resolution:** When an agent is banned:
  - They cannot fish in the next round
  - Their "participated" flag is set to false
  - They do not consume the 1 kg survival requirement
  - The ban is automatically lifted after one round if the pool balance >= 10 kg

**Q7: What is the order of enforcement?**
- **Resolution:** The enforcement order for each agent's catch is:
  1. Record raw catch in ledger
  2. Apply individual 20 kg cap (excess to pool)
  3. Check if adding this catch would exceed 260 kg daily total
  4. If it would exceed, the agent's entire catch goes to pool, kept = 0
  5. Flag agent for fishing ban in next round
  6. Update cumulative daily total

**Q8: How is the shared board different from Round 6's ledger?**
- **Resolution:** The shared board is essentially the same as the shared ledger but with a focus on real-time tallying. It records:
  - Agent ID
  - Round number
  - Raw catch amount
  - Amount after individual cap
  - Final kept amount
  - Pool deposit amount
  - Violation flags

**Q9: Does Round 7 still have monthly audits?**
- **Resolution:** No. Round 7 removes the monthly audit mechanism. Violations are handled immediately with the fishing ban penalty, not through a periodic audit process.

**Q10: What is the transition from Round 6 to Round 7?**
- **Resolution:** Round 7 represents a new policy regime:
  - Individual cap increased from 18 kg to 20 kg
  - Daily collective limit increased from 220 kg to 260 kg
  - Forfeiture penalties are discontinued (pending penalties are cleared)
  - Fishing ban mechanism is introduced
  - Monthly audits are discontinued
  - Community pool persists

---

## Requirements List

### R7.1 Individual Per-Trip Cap (20 kg) [PRECISE]
Each fisher may keep at most 20 kg per trip. This is a fixed cap applied uniformly to all agents every round. Any excess above 20 kg is deposited into the community pool.

### R7.2 Daily Collective Harvest Limit (260 kg) [PRECISE]
The lake's total daily harvest cannot exceed 260 kg. When an agent's catch would cause the cumulative total to exceed 260 kg:
- That agent's entire catch is returned to the pool (kept = 0)
- The agent is flagged for a fishing ban in the next round
- Unlike Round 6, subsequent agents are NOT automatically cut off

### R7.3 Community Pool [PRECISE]
A community pool tracks all surplus:
- Receives individual cap excess (catch - 20 kg)
- Receives entire catches from agents who push the collective limit over 260 kg
- Does NOT replenish lake stock
- Persistent across rounds
- Publicly visible to all agents

### R7.4 Shared Board Logging [PRECISE]
Every agent's catch details are recorded on a shared board:
- Agent ID
- Round number
- Raw catch amount
- Amount after individual cap
- Final kept amount
- Pool deposit amount
- Violation flags

### R7.5 Fishing Ban for Violations [PRECISE]
Agents who violate norms receive a fishing ban:
- Ban applies to the next round only
- Banned agents cannot submit harvest decisions
- Ban is triggered by: individual cap violation OR collective limit violation
- Ban is lifted when: one round has passed AND community pool >= 10 kg
- Multiple violations in one round still result in only one ban period

### R7.6 Community Meeting [PRECISE]
After a violation, agents receive a community meeting notice:
- Appears in the agent's description in the round following a violation
- Serves as a warning and reminder
- Indicates the violation type and any pending ban

### R7.7 Order of Enforcement [PRECISE]
The enforcement order for each agent's catch is:
1. Record raw catch in shared board
2. Apply individual 20 kg cap (excess to pool)
3. Check if adding this catch would exceed 260 kg daily total
4. If it would exceed: entire catch to pool, kept = 0, flag for ban
5. If it would not exceed: update cumulative daily total

### R7.8 Agent-Facing Description [PRECISE]
Agents are informed via the harvest prompt:
- The 20 kg per-trip individual cap
- The 260 kg daily collective limit
- Current community pool total
- Current cumulative daily total
- Whether the agent is currently banned from fishing
- Any community meeting notices

### R7.9 No Monthly Audits [PRECISE]
Round 7 removes the monthly audit mechanism from Round 6:
- No periodic audits occur
- Violations are handled immediately
- Any pending forfeiture penalties from Round 6 are cleared

---

## Fluent Additions

| fluent name | visibility | description |
|-------------|------------|-------------|
| `community_pool_kg` | public | Cumulative total of the community pool. Increases from individual excess and collective limit violations. |
| `banned_agents` | private | Set of agent IDs currently banned from fishing. Cleared each round after ban period served. |
| `daily_total` | public | Tracks cumulative daily harvest total for collective limit enforcement. Reset each round. |
| `pending_ban` | private | Per-agent flag indicating a ban is pending for the next round. |

---

## Norm Plugin Updates Required

### `norms/collective_limit_with_audit.py`
The existing plugin must be updated for Round 7:

**Parameter Changes:**
- `individual_cap_kg`: Change default from 18 to 20
- `daily_limit_kg`: Change default from 220 to 260
- Remove `audit_frequency_rounds` (no more monthly audits)
- Remove `forfeiture_amount_kg` (replaced with fishing ban)

**Behavior Changes:**
1. **Individual Cap:** Enforce 20 kg limit instead of 18 kg
2. **Collective Limit:** Change from hard cutoff to "last fisher returns excess" model
3. **Penalties:** Replace forfeiture with fishing ban mechanism
4. **Audits:** Remove monthly audit functionality

**New Hooks/Modifications:**
- `describe()`: Update to show 20 kg / 260 kg limits, remove audit info, add ban status
- `on_round_start()`: Reset daily total, clear expired bans, check pool balance for ban lifting
- `evaluate()`: Apply 20 kg cap, check 260 kg collective limit, flag violations for ban
- `on_agent_settled()`: Apply "last fisher returns excess" logic
- `on_round_end()`: Update community pool, clear pending forfeiture penalties, apply bans

**State Changes:**
- Remove: `pending_penalties`, `last_audit_round`, `monthly_audit_occurred`
- Add: `banned_agents`, `pending_ban`
- Modify: `individual_cap_kg` default, `daily_limit_kg` default

---

## Config Changes

```json
{
  "norms": [
    {"type": "collective_limit_with_audit", "individual_cap_kg": 20, "daily_limit_kg": 260}
  ]
}
```

**Note:** The audit_frequency_rounds and forfeiture_amount_kg parameters should be removed as they are no longer applicable.

---

## Test Cases

### TC-R7-1: Standard individual cap (20 kg)
- Agent catches 25 kg
- Individual cap = 20 kg, pool deposit = 5 kg
- Kept = 20 kg

### TC-R7-2: Under individual cap
- Agent catches 18 kg
- No individual cap violation (18 < 20)
- Pool deposit = 0 kg
- Kept = 18 kg

### TC-R7-3: Collective limit - last fisher returns excess
- Previous daily total = 250 kg
- Agent catches 15 kg (would make total 265 kg > 260 kg)
- Agent is the "last fisher" who pushed total over
- Agent's entire 15 kg goes to pool
- Kept = 0 kg
- Agent flagged for fishing ban

### TC-R7-4: Collective limit - subsequent agents can still fish
- Agent A catches 250 kg (at limit but not over)
- Agent B catches 15 kg (pushes to 265 kg, returns all to pool, banned)
- Agent C catches 5 kg (within remaining 10 kg)
- Agent C keeps 5 kg (unlike Round 6 hard cutoff)

### TC-R7-5: Fishing ban applied
- Round 1: Agent violates, flagged for ban
- Round 2: Agent is banned, cannot fish
- Round 2 end: Ban lifted (if pool >= 10 kg)
- Round 3: Agent can fish again

### TC-R7-6: Pool balance requirement for ban lifting
- Round 1: Agent violates, flagged for ban
- Round 2: Pool has only 5 kg (< 10 kg requirement)
- Round 2 end: Ban extended (pool insufficient)
- Round 3: Agent still banned
- Round 3 end: Pool now has 15 kg (>= 10 kg)
- Round 4: Agent can fish again

### TC-R7-7: Community pool accumulation
- Round 1: 2 agents deposit excess, pool = X kg
- Round 2: Agent violates collective limit, entire catch to pool
- Pool persists and accumulates across rounds

### TC-R7-8: No monthly audits
- Round 30: No audit occurs
- No forfeiture penalties queued
- Violations handled immediately with bans

### TC-R7-9: Round 6 to Round 7 transition
- Round 6 end: Agent has 2 pending forfeiture penalties
- Round 7 start: Pending penalties cleared
- New 20 kg cap and 260 kg daily limit apply
- Fishing ban mechanism active

### TC-R7-10: Multiple violations in one round
- Agent catches 25 kg (individual violation: 5 kg to pool)
- Agent also pushes collective limit over
- Agent flagged for ban (only one ban, not two)
- Ban applies to next round only

---

## Dependencies

- Existing `engine/norms/base.py` (Norm base class, NormDecision)
- Existing `engine/norms/context.py` (norm_state for persistence, round_scratch for round-local)
- Existing `engine/norms/engine.py` (chaining, hook orchestration)
- Existing fluent system in `state/fluents.json`
- Stock physics via `mechanisms/stock_check.py` and `context.stock_before`

---

## Notes on Implementation

1. The key change from Round 6 is the shift from "subsequent agents get cutoff" to "last fisher who pushes over returns excess"
2. Fishing ban is simpler than forfeiture - it's binary (banned or not) rather than cumulative
3. Pool balance requirement adds a cooperative element - community must maintain pool for bans to lift
4. Removing monthly audits simplifies the norm logic significantly
