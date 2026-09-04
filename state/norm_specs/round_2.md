# Round 2 Norm Specification

## Source Text (from norm.txt)

**Policy:** Each fisher may keep up to 15 kg per trip, but the lake's total harvest per day cannot exceed 200 kg; any excess from a fisher's haul above that threshold must be returned to a community pool.

**Operationalization:** After each trip, fishers log their haul to the shared ledger. If the sum of all hauls that day is ≤200 kg, all fish are kept. If the total >200 kg, the surplus is divided proportionally among fishers and must be returned to the pool. The community will meet weekly to adjust the 200‑kg limit if needed. A fisher who fails to return the required surplus will forfeit 10% of their next trip's haul until the deficit is cleared.

---

## Clarifications & Ambiguities Resolved

**Q1: What constitutes a "day" in this simulation?**
- **Resolution:** One round = one day. The daily collective limit applies per round.

**Q2: What happens to fish "returned to the community pool"?**
- **Resolution:** The community pool represents fish that are not kept by fishers but are also not returned to the lake stock. These fish are effectively set aside for community benefit (e.g., sold for communal funds, distributed to non-fishing community members, or preserved). This is a **new fluent** `community_pool_kg` that tracks the cumulative surplus returned across all rounds. It does NOT regenerate the lake stock.

**Q3: How is "weekly" interpreted in rounds?**
- **Resolution:** For this implementation, the weekly meeting is noted as a future governance mechanism. The initial implementation will use a fixed 200 kg daily limit. The "weekly adjustment" clause is deferred to a future round if needed.

**Q4: How is "failure to return required surplus" detected and tracked?**
- **Resolution:** The surplus return is enforced automatically at the end of each round during `on_round_end()`. Fishers do not have a choice in the matter—their kept amount is adjusted down proportionally. However, to support the penalty clause, we track any **deficit** (amount an agent was supposed to return but didn't due to edge cases or enforcement failure) in per-agent state. For this implementation, deficits arise primarily when an agent's kept amount is less than their assessed surplus contribution (they "owe" more than they have).

**Q5: What is the "deficit" exactly?**
- **Resolution:** A deficit occurs when an agent's proportional surplus share exceeds what they actually caught. In such cases, they return everything they caught (kept becomes 0), and the unfulfilled portion becomes their deficit. They must "clear" this deficit by having 10% of subsequent trips forfeited (not kept) until the cumulative forfeited amount equals the deficit.

---

## Requirements List

### R2.1 Individual Per-Trip Cap [PRECISE]
Each fisher may keep at most 15 kg from their own catch in a single trip, regardless of the collective total.

### R2.2 Daily Collective Limit [PRECISE]
The sum of all fish kept by all fishers in a single round cannot exceed 200 kg.

### R2.3 Shared Ledger Logging [PRECISE]
After each agent's haul is determined, it is logged to a round-wide shared ledger visible to all norms. This ledger tracks each agent's initial catch (after individual cap but before collective adjustment).

### R2.4 Surplus Calculation [PRECISE]
If the sum of all hauls in the shared ledger exceeds 200 kg, the surplus = total - 200 kg. This surplus must be returned to the community pool.

### R2.5 Proportional Redistribution [PRECISE]
The surplus is divided proportionally among fishers based on their contribution to the total:
- For each fisher, their proportional share of the surplus = (their haul / total hauls) × surplus
- Their final kept amount = their haul - their proportional surplus share
- If their proportional share exceeds their haul, they keep 0 and the excess becomes their deficit

### R2.6 Community Pool Fluent [PRECISE]
A new fluent `community_pool_kg` tracks the cumulative total of all surplus returned across all rounds. It is public and visible to all agents.

### R2.7 Deficit Tracking [PRECISE]
Per-agent persistent state tracks any deficit (unfulfilled surplus obligation). Deficits carry over across rounds until cleared.

### R2.8 Penalty for Uncleared Deficits [PRECISE]
An agent with a non-zero deficit forfeits 10% of their next trip's haul (applied after physics, before other norms). The forfeited amount is:
- Subtracted from their kept kg
- Added to the community pool
- Subtracted from their outstanding deficit (reducing it)
- Continues until deficit reaches zero

### R2.9 Deficit Clearing Order [PRECISE]
Penalties are applied round-by-round. In each round where an agent has a deficit:
1. Calculate their raw catch from effort
2. Forfeit 10% of raw catch (add to pool, subtract from deficit)
3. Continue with remaining norms on the reduced amount

### R2.10 Agent-Facing Description [PRECISE]
Agents are informed via the harvest prompt:
- The 15 kg individual cap
- The 200 kg daily collective limit
- Current round's community pool total
- Their personal deficit status (if any)

---

## Fluent Additions

| fluent name | visibility | description |
|-------------|------------|-------------|
| `community_pool_kg` | public | Cumulative total of surplus returned to community pool across all rounds. Updated at end of each round. |
| `pool_deficit` | private | Per-agent outstanding deficit (amount still owed to community pool from previous rounds). Carries across rounds. |

---

## New Norm Plugins Required

### `norms/daily_collective_limit.py`
Implements the collective daily limit with proportional surplus redistribution.

**Type name:** `daily_collective_limit`

**Parameters:**
- `daily_limit_kg` (default: 200): The maximum total harvest allowed per round
- `individual_cap_kg` (default: 15): Maximum per-agent per-round keep

**Hooks:**
- `describe()`: Inform agents of the daily limit and current pool total
- `evaluate()`: Apply individual cap first, then track in round_scratch for collective calculation
- `on_round_end()`: Calculate surplus, redistribute proportionally, update community_pool_kg fluent, track deficits

### `norms/deficit_penalty.py`
Implements the 10% penalty for agents with outstanding deficits.

**Type name:** `deficit_penalty`

**Parameters:**
- `penalty_rate` (default: 0.10): Fraction of catch forfeited when deficit exists

**Hooks:**
- `evaluate()`: Check for deficit, apply 10% forfeiture if present, reduce deficit accordingly
- `describe()`: Inform agent of their deficit status if non-zero

---

## Config Changes

```json
{
  "norms": [
    {"type": "deficit_penalty", "penalty_rate": 0.10},
    {"type": "daily_collective_limit", "daily_limit_kg": 200, "individual_cap_kg": 15}
  ]
}
```

**Ordering rationale:**
- `deficit_penalty` must run BEFORE `daily_collective_limit` because:
  1. The penalty applies to the "next trip's haul" — meaning it should be applied first to the raw catch
  2. After penalty, the remaining amount goes through the normal cap and collective limit process

---

## Test Cases

### TC-R2-1: Under collective limit
- 5 agents each catch 30 kg (after effort)
- Individual cap reduces each to 15 kg
- Total = 75 kg ≤ 200 kg
- All keep 15 kg, community pool += 0

### TC-R2-2: Over collective limit, proportional split
- 10 agents each catch 30 kg (after effort)
- Individual cap reduces each to 15 kg
- Subtotal = 150 kg ≤ 200 kg, no surplus yet
- Wait: need scenario where total exceeds 200 after individual cap

### TC-R2-3: Collective limit exceeded
- 20 agents each catch 30 kg (after effort)
- Individual cap reduces each to 15 kg
- Subtotal = 300 kg > 200 kg, surplus = 100 kg
- Each agent's share = (15/300) × 100 = 5 kg
- Each agent keeps 15 - 5 = 10 kg
- Community pool += 100 kg

### TC-R2-4: Deficit accrual (edge case)
- Agent A catches 2 kg (after effort)
- Individual cap: keeps 2 kg (under 15)
- Collective scenario: 20 agents, total 300 kg after caps
- Surplus = 100 kg
- Agent A's proportional share = (2/300) × 100 = 0.67 kg
- Agent A can only return 2 kg, keeps 0, deficit = 0 (they contributed everything)

### TC-R2-5: Penalty application
- Agent B has deficit of 5 kg from previous round
- Agent B catches 20 kg this round
- Deficit penalty: forfeits 10% = 2 kg, deficit reduces to 3 kg
- Remaining 18 kg goes to individual cap (reduced to 15 kg)
- Community pool += 2 kg (from penalty)

### TC-R2-6: Deficit fully cleared
- Agent C has deficit of 1 kg
- Agent C catches 20 kg
- Deficit penalty: forfeits 10% = 2 kg, but deficit is only 1 kg
- Only 1 kg forfeited, deficit cleared, remaining 19 kg proceeds

---

## Dependencies

- Existing `engine/norms/base.py` (Norm base class, NormDecision)
- Existing `engine/norms/context.py` (norm_state for persistence, round_scratch for round-local)
- Existing `engine/norms/engine.py` (chaining, hook orchestration)
- Existing fluent system in `state/fluents.json`
- New fluents to be added: `community_pool_kg` (global), `pool_deficit` (per-agent)
