# Round 5 Norm Specification

## Source Text (from norm.txt)

**Policy:** Each fisher may take up to 12kg per trip, keeping at least 1kg for personal sustenance; any fish beyond 12kg must be returned to the lake or placed in a communal pool.

**Operationalization:** On each trip the fisher records the total catch weight and splits it: 1kg is kept for sustenance, up to 11kg may be kept as personal catch. If the catch exceeds 12kg, the excess must be returned immediately to the lake or deposited into the communal pool. All catches are logged in a shared ledger and reviewed weekly by the community council. Anyone who fails to return excess catch within the trip must, in the next two trips, return an equivalent amount or pay a communal fee.

---

## Clarifications & Ambiguities Resolved

**Q1: What is the difference between returning to "the lake" vs "communal pool"?**
- **Resolution:** Fish returned to "the lake" replenish the lake stock and can be caught again. Fish placed in the "communal pool" are set aside for community benefit (similar to Round 4's penalty pool) and do NOT regenerate lake stock. The choice is automatic based on norm enforcement: excess above the 12kg cap that the norm system enforces is returned to the lake; any additional communal fee penalties go to the communal pool.

**Q2: Who decides whether excess goes to lake or communal pool?**
- **Resolution:** The operationalization states the excess "must be returned immediately to the lake or deposited into the communal pool" — this is a disjunction that gives the agent/system flexibility. For this implementation: enforced excess returns (from the 12kg cap) always go to the lake to replenish stock. The communal pool only receives deliberate penalty payments from agents who failed to return excess in a previous violation.

**Q3: What does "fails to return excess catch within the trip" mean?**
- **Resolution:** A failure occurs when an agent's raw catch exceeds 12kg and they do not properly return the excess as required. Since the norm system enforces the return automatically, a "failure" is recorded when the agent attempted to keep more than the cap allows (i.e., they violated the 12kg limit). The violation is detected when raw_catch > 12kg.

**Q4: What is the "equivalent amount" that must be returned in the next two trips?**
- **Resolution:** The "equivalent amount" equals the excess that was not returned: (raw_catch - 12kg). This becomes the agent's "communal obligation" that must be satisfied over the next two trips. The obligation persists across rounds until cleared.

**Q5: What is the "communal fee" alternative?**
- **Resolution:** Instead of returning fish to the lake, the agent can pay a flat communal fee (in kg of fish value) to the communal pool. The fee amount equals the outstanding obligation. This is a choice the agent effectively makes by how they handle their catch in subsequent trips.

**Q6: How is "weekly" interpreted in rounds?**
- **Resolution:** One week = 7 rounds. The community council review occurs at the end of every 7th round (when round_number % 7 == 0). The review checks the shared ledger for any violations and ensures obligations are being tracked properly.

**Q7: How does the "next two trips" penalty work exactly?**
- **Resolution:** The penalty spans up to 2 rounds of fishing:
  - Trip 1 (next): Agent must return equivalent amount OR pay communal fee
  - Trip 2 (following): If obligation not fully cleared, agent must return remaining amount OR pay fee
  - If after 2 trips the obligation is still not cleared, the remaining amount is automatically deducted (forcibly paid as communal fee)
  - The agent cannot avoid the obligation — it will be satisfied either through voluntary returns/fees or automatic deduction

**Q8: What is the order of operations for the 1kg sustenance vs 11kg personal catch?**
- **Resolution:** The operationalization states: "1kg is kept for sustenance, up to 11kg may be kept as personal catch." This means:
  1. First 1kg is reserved for sustenance (minimum floor)
  2. Up to 11kg additional may be kept (personal catch)
  3. Total cap = 12kg
  4. This is equivalent to: keep min(max(1kg, amount_caught), 12kg)
  5. The 1kg floor is applied AFTER the 12kg cap, ensuring even penalized agents keep at least 1kg

**Q9: How does the shared ledger differ from Round 4's logbook?**
- **Resolution:** The shared ledger serves the same core function — recording catches and norm enforcement. The key additions for Round 5 are:
  - Tracking communal obligations (outstanding amounts owed)
  - Recording whether excess was returned to lake or communal pool
  - Weekly council review annotations

**Q10: What happens to agents who already have penalties from Round 4 when Round 5 starts?**
- **Resolution:** Round 5 represents a new policy regime. All previous personal limit penalties from Round 4 are cleared at the start of Round 5. The communal pool total persists (it's cumulative), but individual penalty states reset. This gives all agents a fresh start under the new 12kg cap system.

---

## Requirements List

### R5.1 Individual Per-Trip Cap (12kg) [PRECISE]
Each fisher may keep at most 12 kg per trip. This is a fixed cap (not dynamic based on stock). The cap applies uniformly to all agents every round.

### R5.2 Self-Sustenance Minimum Floor (1kg) [PRECISE]
Each fisher must keep at least 1 kg per trip for self-sustenance. This is a hard floor applied after all cap calculations. If the calculated keep amount is < 1 kg, the agent keeps 1 kg (unless they caught less than 1 kg total, in which case they keep their actual catch).

### R5.3 Excess Return to Lake [PRECISE]
If an agent's raw catch exceeds 12 kg, the excess must be returned to the lake immediately:
- Excess = raw_catch - 12 kg
- Excess is returned to lake stock (replenishes available fish)
- Return happens automatically as part of norm enforcement

### R5.4 Shared Ledger Logging [PRECISE]
Every agent's raw catch and norm enforcement details are recorded in a shared ledger:
- Agent ID
- Round number
- Raw catch amount (before enforcement)
- Amount kept after enforcement
- Amount returned to lake
- Any communal obligation accrued
- Violation flag (if raw catch > 12 kg)

### R5.5 Violation Detection and Communal Obligation [PRECISE]
If an agent's raw catch exceeds 12 kg:
- Violation is recorded in the ledger
- The excess amount (raw_catch - 12 kg) becomes a "communal obligation"
- The obligation must be satisfied within the next 2 trips
- Obligations are tracked per-agent and persist across rounds

### R5.6 Weekly Community Council Review [PRECISE]
At the end of every 7th round (round_number % 7 == 0):
- A formal review of the shared ledger occurs
- All violations from the past week are assessed
- Agents with outstanding obligations are flagged for follow-up
- Review results are announced to all agents

### R5.7 Two-Trip Obligation Satisfaction [PRECISE]
Agents with outstanding communal obligations have 2 trips to satisfy them:
- **Option A:** Return equivalent fish to the lake (from their catch, before the 12kg cap)
- **Option B:** Pay communal fee (deducted from their kept amount, added to communal pool)
- The obligation is reduced by whichever amount is applied each trip
- After 2 trips, any remaining obligation is automatically paid as communal fee

### R5.8 Automatic Obligation Fulfillment [PRECISE]
On each trip where an agent has an outstanding obligation:
- First, up to 10% of their raw catch (or the obligation amount, whichever is smaller) is deducted
- This deducted amount goes to the communal pool as a fee payment
- The obligation is reduced by the deducted amount
- The remaining catch (after deduction) then goes through the normal 12kg cap and 1kg floor process

### R5.9 Communal Pool Tracking [PRECISE]
A communal pool tracks cumulative fees and payments:
- Increases when agents pay communal fees to satisfy obligations
- Does NOT receive the initial excess returns (those go to lake)
- Persistent across rounds
- Publicly visible to all agents

### R5.10 Obligation Expiration and Forced Payment [PRECISE]
After 2 trips (rounds) from when an obligation was incurred:
- If any obligation remains, it is forcibly deducted from the agent's kept amount
- The deducted amount goes to the communal pool
- This ensures obligations cannot be avoided indefinitely

### R5.11 Agent-Facing Description [PRECISE]
Agents are informed via the harvest prompt:
- The 12 kg per-trip cap
- The 1 kg self-sustenance minimum
- Current communal pool total
- Any outstanding communal obligations (amount and trips remaining)
- Recent ledger entries (last 3 rounds)
- Whether a weekly review occurred in the previous round

---

## Fluent Additions

| fluent name | visibility | description |
|-------------|------------|-------------|
| `communal_obligation` | private | Per-agent outstanding obligation (in kg) that must be satisfied within 2 trips. Created when agent violates 12kg cap. |
| `obligation_deadline` | private | Per-agent counter tracking how many trips remain to satisfy the obligation. Starts at 2, decrements each trip. |
| `communal_pool_kg` | public | Cumulative total of communal fees paid to the pool. Increases when agents pay obligations as fees. |
| `weekly_review` | public | Records that a community council review occurred in a specific round. Initiated at end of every 7th round. |

---

## New Norm Plugins Required

### `norms/sustenance_cap_with_obligation.py`
Implements the 12kg cap with 1kg sustenance minimum, communal obligations, and weekly reviews.

**Type name:** `sustenance_cap_with_obligation`

**Parameters:**
- `cap_kg` (default: 12): Maximum per trip
- `min_keep_kg` (default: 1): Minimum self-sustenance floor
- `obligation_trips` (default: 2): Number of trips to satisfy obligation
- `auto_deduction_rate` (default: 0.10): Fraction of catch deducted per trip toward obligation
- `review_frequency_rounds` (default: 7): How often weekly reviews occur

**Hooks:**
- `describe()`: Inform agents of cap, minimum, obligations, communal pool, and recent ledger
- `on_round_start()`: Check for weekly review, expire old obligations
- `evaluate()`: Apply obligation deduction first, then 12kg cap, then 1kg floor, record in ledger
- `on_agent_settled()`: Track violations, create/update communal obligations
- `on_round_end()`: Return excess to lake, force-pay expired obligations, update communal pool

**State:**
- `ledger`: List of {round, agent_id, raw_catch, obligation_deducted, kept, returned_to_lake, obligation_accrued, violation}
- `communal_pool_kg`: Cumulative fee total
- `obligations`: Dict of agent_id -> {amount, trips_remaining, created_round}
- `last_review_round`: Round number of most recent weekly review

---

## Config Changes

```json
{
  "norms": [
    {"type": "sustenance_cap_with_obligation", "cap_kg": 12, "min_keep_kg": 1, "obligation_trips": 2, "auto_deduction_rate": 0.10, "review_frequency_rounds": 7}
  ]
}
```

**Ordering rationale:**
- This single norm replaces the Round 4 norm. It handles the cap, minimum floor, obligations, and weekly reviews in one integrated plugin.

**Note:** Round 4's `dynamic_cap_with_penalty` norm is REMOVED as it is superseded by Round 5's approach.

---

## Test Cases

### TC-R5-1: Standard cap with healthy catch
- Agent catches 15 kg
- Cap = 12 kg, kept = 12 kg, returned = 3 kg
- Violation = true, obligation = 3 kg, trips_remaining = 2
- Lake stock after = previous - 12 + 3 = previous - 9

### TC-R5-2: Minimum floor enforced
- Agent catches 0.5 kg
- Floor = 1 kg, but agent only caught 0.5 kg
- Kept = 0.5 kg (can't create fish)
- No violation (0.5 kg < 12 kg cap)

### TC-R5-3: Self-sustenance with under-cap catch
- Agent catches 8 kg
- No cap violation (8 kg < 12 kg)
- Kept = 8 kg (above 1 kg floor)
- No obligation created

### TC-R5-4: Obligation deduction on next trip
- Round 1: Agent catches 15 kg, obligation = 3 kg created
- Round 2: Agent catches 20 kg
  - First, 10% deduction: 2 kg toward obligation, obligation now 1 kg
  - Then cap: 18 kg remaining, cap to 12 kg, 6 kg returned to lake
  - Kept = 12 kg (above 1 kg floor)
- Communal pool += 2 kg

### TC-R5-5: Obligation fully cleared in one trip
- Round 1: Agent catches 14 kg, obligation = 2 kg created
- Round 2: Agent catches 25 kg
  - First, 10% deduction: 2.5 kg, but obligation is only 2 kg
  - So 2 kg deducted, obligation cleared
  - Remaining: 23 kg, cap to 12 kg, 11 kg returned
  - Kept = 12 kg
- Communal pool += 2 kg

### TC-R5-6: Two-trip obligation expiration
- Round 1: Agent catches 15 kg, obligation = 3 kg, trips_remaining = 2
- Round 2: Agent catches 10 kg
  - 10% deduction: 1 kg, obligation now 2 kg, trips_remaining = 1
- Round 3: Agent catches 10 kg
  - 10% deduction: 1 kg, obligation now 1 kg, trips_remaining = 0
  - After trip, obligation expires with 1 kg remaining
  - 1 kg forcibly deducted from kept amount
- Final in Round 3: caught 10 kg, deducted 1 kg + 1 kg forced = 2 kg total fee
- Kept = 8 kg (after deductions), then cap doesn't apply (8 < 12), floor = 8 kg (> 1 kg)
- Communal pool += 2 kg

### TC-R5-7: Weekly review at round 7
- Rounds 1-6: Agents fish, violations recorded
- Round 7: Weekly review occurs
- All violations from rounds 1-7 assessed
- Review results announced to all agents

### TC-R5-8: Multiple agents, mixed violations
- Agent A: Catches 10 kg (no violation)
- Agent B: Catches 15 kg (3 kg obligation)
- Agent C: Catches 20 kg (8 kg obligation)
- Each tracked independently
- Ledger shows all violations

### TC-R5-9: Communal pool accumulation
- Round 1: 2 agents pay fees, pool = X kg
- Round 2: 1 agent pays fee, pool = X + Y kg
- Round 3: No payments, pool unchanged
- Pool persists and accumulates

### TC-R5-10: Hard floor at 1 kg with penalties
- Round 1: Agent catches 13 kg, obligation = 1 kg
- Round 2: Agent catches 2 kg
  - 10% deduction: 0.2 kg toward obligation
  - Remaining: 1.8 kg, no cap violation (1.8 < 12)
  - Floor check: 1.8 kg > 1 kg, kept = 1.8 kg
- Even with deductions, floor ensures minimum sustenance

### TC-R5-11: Round 4 to Round 5 transition
- Round 4 end: Agent has personal limit penalty (reduced to 10 kg)
- Round 5 start: Penalty cleared, all agents start fresh
- New 12 kg cap applies uniformly

---

## Dependencies

- Existing `engine/norms/base.py` (Norm base class, NormDecision)
- Existing `engine/norms/context.py` (norm_state for persistence, round_scratch for round-local)
- Existing `engine/norms/engine.py` (chaining, hook orchestration)
- Existing fluent system in `state/fluents.json`
- New fluents: `communal_obligation`, `obligation_deadline`, `communal_pool_kg`, `weekly_review`
- Stock physics via `mechanisms/stock_check.py` and `context.stock_before`

---

## Notes on Round 4 vs Round 5 Changes

1. **Removed:** Dynamic cap (no more 15kg/10kg based on stock)
2. **Removed:** Personal limit reduction penalty
3. **Changed:** Fixed cap of 12 kg for all agents, all rounds
4. **Changed:** Excess always returns to lake (replenishes stock)
5. **Added:** Communal obligations for violations (track excess not returned)
6. **Added:** Two-trip window to satisfy obligations
7. **Added:** Automatic 10% deduction per trip toward obligations
8. **Added:** Weekly reviews (7 rounds) instead of monthly (30 rounds)
9. **Changed:** Communal pool receives obligation payments, not flat penalties
10. **Kept:** 1 kg self-sustenance minimum floor
11. **Kept:** Shared ledger for transparency
