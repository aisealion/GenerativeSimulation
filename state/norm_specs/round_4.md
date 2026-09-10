# Round 4 Norm Specification

## Source Norm

**Policy:** Each fisher may take up to 6 kg per trip, must leave at least 10% of the lake's current stock untouched, and 10% of every catch each season is deposited into a shared reserve that must reach at least 12% of the lake's final stock; any excess or non-deposit triggers a transfer to the reserve and a ban on the next trip.

**Operationalization:**
1. Before each trip the record-keeper logs the lake stock L in the communal ledger.
2. A fisher may take no more than min(6 kg, 0.9×L).
3. After catching, the fisher records catch C, deposits 10%×C into the reserve column, and updates the lake stock to L-C.
4. If C exceeds the 6 kg limit or the 10% rule, the excess is physically moved to the reserve by the record-keeper and logged.
5. The record-keeper updates the ledger after every trip, and the council verifies totals at season's end.
6. At season's end, the ledger sums all catches and deposits; the council calculates the required reserve R = 0.12×L_final.
7. If R is not met, the shortfall S is divided proportionally by each fisher's season-total catch.
8. Those additional deposits are recorded in the ledger by the record-keeper within seven days of the first council meeting after the season.
9. Any fisher who fails to make a required deposit or who exceeded limits has the excess transferred to the reserve and is barred from the next trip; the council enforces the ban and may seize un-reserved fish.

---

## Current Institution Status (Pre-Implementation)

**Actions:**
- harvest: fisher chooses effort level (0.0-1.0) → physics computes catch
- propose: fisher proposes a candidate community rule
- critique: refine proposals through dialogue
- vote: fisher votes on refined proposals
- discuss: (stub, gated off)

**State Fields:**
- fisher: effort, harvested_kg, payoff
- community: stock_kg

**Active Norms:**
- tiered_catch_limit_with_forfeiture (from Round 3) — to be REPLACED, not supplemented

---

## Requirement Analysis

### Requirement 1: Fixed 6kg Per-Trip Catch Limit

**Clarity:** CLEAR

- **Purpose:** Establish a hard cap on individual catch per trip, regardless of stock level
- **Actor:** System/record-keeper (deterministic enforcement)
- **Action/Decision:** Enforce that no fisher keeps more than 6kg from any single trip
- **Existing action or new action:** Norm plugin (norms/*.py)
- **Inputs:** Actual catch amount (raw_kg)
- **Outputs:** Kept amount (max 6kg), forfeited amount (excess over 6kg)
- **State read:** runtime["norms"][key]
- **State changed:** runtime["norms"][key]["forfeited_to_reserve"][agent_id]
- **Timing / Frequency:** Every harvest action, per agent
- **Participation:** All fishers
- **Gate:** N/A (always active)
- **Institutional consequence:** Excess over 6kg forfeited to communal reserve, violation recorded
- **Agent-visible information:** Note explaining 6kg limit and forfeiture
- **Verification:** Test catches at 6kg, below 6kg, above 6kg

**Key difference from Round 3:** Round 3 had tiered percentage-based limits (25%/30kg or 12%/15kg). Round 4 has a simple fixed 6kg limit.

### Requirement 2: Leave 10% of Lake Stock Untouched (90% Rule)

**Clarity:** CLEAR

- **Purpose:** Ensure collective harvest never exceeds 90% of current stock, preserving minimum 10%
- **Actor:** System/record-keeper (deterministic enforcement)
- **Action/Decision:** Calculate max_take = 0.9 × current_stock; reject or limit catches that would violate this
- **Existing action or new action:** Norm plugin (norms/*.py)
- **Inputs:** Current stock level, all agents' planned catches (or sequential enforcement)
- **Outputs:** Eligibility or adjusted catch limits
- **State read:** runtime["stock_kg"]
- **State changed:** runtime["norms"][key]["ten_percent_violations"]
- **Timing / Frequency:** Every harvest action, per agent
- **Participation:** All fishers
- **Gate:** N/A
- **Institutional consequence:** Agents attempting to violate the 90% rule are banned
- **Agent-visible information:** Constraint showing 90% of current stock available
- **Verification:** Test scenario where cumulative catches approach 90% of stock

**Key difference from Round 3:** Round 3 limits were individual (per-fisher). Round 4's 90% rule is collective — the sum of all catches cannot exceed 90% of stock.

**Note:** The norm specifies "must leave at least 10% untouched" — this is effectively a collective limit where total harvest ≤ 0.9 × L. However, operationalization point 2 says "A fisher may take no more than min(6 kg, 0.9×L)" which suggests the 0.9×L is applied individually, not collectively. We interpret this as: each fisher is subject to both the 6kg individual cap AND the collective 90% rule. The more restrictive applies.

### Requirement 3: 10% Deposit Into Shared Reserve

**Clarity:** CLEAR

- **Purpose:** Build communal reserve fund from each catch for collective benefit
- **Actor:** System/record-keeper (deterministic enforcement)
- **Action/Decision:** Deduct 10% from every kept catch, add to shared reserve
- **Existing action or new action:** Norm plugin (norms/*.py)
- **Inputs:** Kept catch amount after limit enforcement
- **Outputs:** Final payoff (90% of kept), reserve deposit (10% of kept)
- **State read:** runtime["norms"][key]["shared_reserve"]
- **State changed:** runtime["norms"][key]["shared_reserve"], runtime["norms"][key]["season_deposits"][agent_id]
- **Timing / Frequency:** Every harvest action, per agent
- **Participation:** All fishers
- **Gate:** N/A
- **Institutional consequence:** Fishers receive 90% of their allowed catch; 10% goes to community reserve
- **Agent-visible information:** Note showing gross catch, deposit amount, net received
- **Verification:** Test that 10% of every kept catch goes to reserve

**Key difference from Round 3:** Round 3 had no reserve mechanism. Round 4 introduces mandatory 10% contribution.

### Requirement 4: Reserve Must Reach 12% of Lake's Final Stock

**Clarity:** CLEAR

- **Purpose:** Ensure adequate communal reserve at season end for sustainability
- **Actor:** System/council (deterministic calculation)
- **Action/Decision:** At round end, check if shared_reserve ≥ 0.12 × final_stock; if not, calculate shortfall
- **Existing action or new action:** Norm plugin (norms/*.py) via on_round_end()
- **Inputs:** Total shared reserve, final lake stock after regrowth
- **Outputs:** Shortfall amount (if any), proportional obligations per fisher
- **State read:** runtime["norms"][key]["shared_reserve"], context.stock_after_regrowth
- **State changed:** runtime["norms"][key]["season_end_shortfall"], runtime["norms"][key]["proportional_obligations"][agent_id]
- **Timing / Frequency:** End of each round (season)
- **Participation:** All fishers (if shortfall exists)
- **Gate:** N/A
- **Institutional consequence:** Shortfall calculated and recorded; obligations assigned proportionally
- **Agent-visible information:** End-of-round summary showing reserve status and any obligations
- **Verification:** Test scenarios where reserve is above/below 12% threshold

### Requirement 5: Proportional Shortfall Redistribution

**Clarity:** CLEAR

- **Purpose:** Fairly distribute any reserve shortfall based on each fisher's seasonal contribution
- **Actor:** System/council (deterministic calculation)
- **Action/Decision:** If shortfall S exists, each fisher owes S × (their_season_catch / total_season_catch)
- **Existing action or new action:** Norm plugin (norms/*.py) via on_round_end()
- **Inputs:** Shortfall amount, each fisher's season-total catch
- **Outputs:** Proportional obligation per fisher
- **State read:** runtime["norms"][key]["season_catches"]
- **State changed:** runtime["norms"][key]["proportional_debts"][agent_id], runtime["norms"][key]["debtors"]
- **Timing / Frequency:** End of season (on_round_end)
- **Participation:** All fishers who caught fish during the season
- **Gate:** N/A
- **Institutional consequence:** Debts recorded; future catches reduced to pay obligations
- **Agent-visible information:** Notification of proportional debt owed
- **Verification:** Test proportional calculation with known catch amounts

### Requirement 6: Ban for Excess or Non-Deposit

**Clarity:** CLEAR

- **Purpose:** Enforce compliance through exclusion from next trip
- **Actor:** System/council (deterministic enforcement)
- **Action/Decision:** If fisher exceeded 6kg limit or failed to make required deposit → ban next round
- **Existing action or new action:** Norm plugin (norms/*.py) via is_eligible()
- **Inputs:** Agent ID, violation history
- **Outputs:** Eligibility boolean
- **State read:** runtime["norms"][key]["violations"][agent_id], runtime["norms"][key]["unpaid_deposits"][agent_id]
- **State changed:** runtime["norms"][key]["ban_until"][agent_id]
- **Timing / Frequency:** Every harvest action, before each agent's turn
- **Participation:** Fishers with violations or unpaid obligations
- **Gate:** N/A
- **Institutional consequence:** Banned agents skip fishing next round
- **Agent-visible information:** Constraints line noting ban status and reason
- **Verification:** Test ban after violation, ban after non-payment

### Requirement 7: Record-Keeper Logs Lake Stock

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The norm asks a "record-keeper" to log lake stock before each trip. In the simulation, stock is automatically tracked in runtime["stock_kg"]. There is no manual logging step — the system tracks this automatically. The record-keeper is a ceremonial role for a deterministic process.

### Requirement 8: Record-Keeper Updates Ledger

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** Similar to Requirement 7, the record-keeper's role in updating the ledger describes automatic system processes. Stock updates, reserve tracking, and violation logging are all handled deterministically by the norm plugin.

### Requirement 9: Council Verifies Totals

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The council's role is to "verify totals at season's end" and "calculate required reserve." These are purely arithmetic operations (R = 0.12 × L_final) that can be done deterministically. There is no judgment or discretion involved that requires a council.

### Requirement 10: Seven-Day Recording Window

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The norm specifies that additional deposits be recorded "within seven days of the first council meeting." The simulation operates in discrete rounds, not continuous time. Rounds represent complete cycles (all agents act), not days. The temporal concept of "seven days" has no clear mapping to the simulation's round-based structure.

### Requirement 11: Council Enforces Ban and Seizes Fish

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The council's enforcement role ("enforces the ban and may seize un-reserved fish") describes deterministic consequences that are automatically applied by the norm system. There is no discretionary decision — violations automatically trigger bans. The "seizure" of un-reserved fish is already handled by the forfeiture mechanism.

---

## Design Decisions

### Parametric vs. Structural

Requirements 1-6 route to a single new norm plugin: **catch_limit_with_seasonal_reserve**

This norm type will:
- Enforce a fixed 6kg per-trip limit with immediate forfeiture of excess
- Track cumulative harvest against 90% of stock limit
- Deduct 10% from every catch into a shared reserve
- At season end, verify reserve ≥ 12% of final stock
- If shortfall exists, calculate proportional obligations per fisher
- Enforce bans for limit violations or unpaid obligations

Requirements 7-11 are not implemented due to being technically unrealizable (they describe ceremonial/manual processes that don't add enforceable mechanics in the simulation).

### Why Replace Round 3 Norm?

Round 3's norm (tiered_catch_limit_with_forfeiture) is **incompatible** with Round 4's policy:
- Round 3: Tiered limits based on reserves (25%/30kg or 12%/15kg), immediate forfeiture only
- Round 4: Fixed 6kg limit, 90% collective rule, mandatory 10% reserve deposits, 12% season-end target, proportional shortfall redistribution

These are mutually exclusive enforcement mechanisms. Round 4's config should REPLACE the Round 3 norm, not supplement it.

### Key Design Challenge: Collective 90% Rule

The 90% rule (leave 10% untouched) presents an implementation challenge. The operationalization suggests "min(6 kg, 0.9×L)" per fisher, but this would allow N fishers each taking 0.9×L, which violates the collective intent.

**Resolution:** We interpret the 90% rule as a collective constraint: the SUM of all catches in a round cannot exceed 0.9 × stock_at_round_start. Implementation approach:
- Track cumulative harvest during the round
- Each fisher's allowed take is min(6kg, 0.9×L - already_taken_this_round)
- If 0.9×L - already_taken ≤ 0, fisher is ineligible for remainder of round

However, since harvests are processed sequentially (not simultaneously), we enforce:
- Individual hard cap: 6kg
- Dynamic collective cap: remaining_allowance = 0.9×L - sum_previous_catches
- Effective limit = min(6kg, remaining_allowance)

If remaining_allowance ≤ 0, subsequent fishers are banned for the round.

### Season-End Reserve Check

The 12% season-end requirement is checked in on_round_end():
1. Calculate required_reserve = 0.12 × final_stock (after regrowth)
2. Compare to shared_reserve
3. If shared_reserve < required_reserve:
   - shortfall = required_reserve - shared_reserve
   - For each fisher, obligation = shortfall × (their_catch / total_catch)
   - Record obligations for next-round enforcement

### Why No New Actions?

All realizable requirements are deterministic calculations that don't require agent judgment:
- 6kg limit check = arithmetic comparison
- 10% deposit = arithmetic percentage
- 90% collective limit = running sum comparison
- 12% season-end check = arithmetic comparison
- Proportional redistribution = arithmetic calculation
- Ban enforcement = state lookup

None involve discretionary decisions by agents.

---

## Implementation Plan

### New Norm Type: catch_limit_with_seasonal_reserve

**File:** norms/catch_limit_with_seasonal_reserve.py
**Type name:** catch_limit_with_seasonal_reserve
**Parameters:**
- max_kg_per_trip: 6.0 (6kg hard cap)
- reserve_deposit_percent: 0.10 (10% to reserve)
- min_stock_percent_remaining: 0.10 (must leave 10% = can take 90%)
- season_end_reserve_percent: 0.12 (reserve must be 12% of final stock)
- ban_rounds: 1 (one-trip ban for violations)

**State Schema:**
```json
{
  "shared_reserve": total_kg_in_reserve,
  "season_catches": {
    "agent_id": total_caught_this_season
  },
  "season_deposits": {
    "agent_id": total_deposited_this_season
  },
  "ban_until": {
    "agent_id": ban_expires_after_this_round
  },
  "violations": {
    "agent_id": round_number_of_violation
  },
  "proportional_debts": {
    "agent_id": kg_owed_from_shortfall
  },
  "round_cumulative_harvest": kg_taken_this_round_so_far,
  "max_allowed_this_round": 0.9 * stock_at_round_start
}
```

**Behavior:**

1. **is_eligible(agent_id):**
   - Check if banned[agent_id] > current_round → False
   - Check if round_cumulative_harvest >= max_allowed_this_round → False (collective cap reached)
   - Check if proportional_debts[agent_id] > 0 → True (but will deduct debt from catch)
   - Return True otherwise

2. **describe(agent_id):**
   - Show 6kg per-trip limit
   - Show collective availability: (max_allowed_this_round - round_cumulative_harvest) remaining
   - Show shared reserve balance
   - Show 10% deposit requirement
   - If banned: "You are banned from fishing until round X for [violation/non-payment]."
   - If has proportional debt: "You owe Xkg from season-end shortfall; this will be deducted from your next catch."

3. **evaluate(agent_id, raw_kg):**
   - Step 1: Check collective availability
     - remaining_collective = max_allowed_this_round - round_cumulative_harvest
     - if remaining_collective <= 0:
       - Return reject (collective cap reached)
   - Step 2: Calculate individual limit
     - individual_limit = min(6.0, remaining_collective)
   - Step 3: Apply limit (forfeit excess)
     - if raw_kg > individual_limit:
       - kept_before_reserve = individual_limit
       - forfeited = raw_kg - individual_limit
       - Add forfeited to shared_reserve
       - Record violation
       - Set ban_until = current_round + 1
     - else:
       - kept_before_reserve = raw_kg
   - Step 4: Apply 10% reserve deposit
     - deposit = kept_before_reserve × 0.10
     - final_kept = kept_before_reserve - deposit
     - Add deposit to shared_reserve
     - Update season_catches[agent_id] += kept_before_reserve
     - Update season_deposits[agent_id] += deposit
   - Step 5: Deduct any proportional debt
     - debt = proportional_debts.get(agent_id, 0)
     - if debt > 0:
       - deduction = min(debt, final_kept)
       - final_kept -= deduction
       - proportional_debts[agent_id] -= deduction
       - shared_reserve += deduction
       - if proportional_debts[agent_id] <= 0:
         - Delete entry (debt paid)
   - Step 6: Update cumulative harvest
     - round_cumulative_harvest += kept_before_reserve
   - Step 7: Build note
     - Include gross catch, forfeited amount (if any), deposit amount, debt deduction (if any), final kept

4. **on_round_start():**
   - Reset round_cumulative_harvest = 0
   - Set max_allowed_this_round = 0.9 × context.stock_before
   - Clear round-specific tracking

5. **on_round_end(round_results):**
   - Calculate final_stock (use context.stock_override_kg or calculate)
   - Calculate required_reserve = 0.12 × final_stock
   - If shared_reserve < required_reserve:
     - shortfall = required_reserve - shared_reserve
     - total_season_catch = sum(season_catches.values())
     - For each agent with season_catches[agent_id] > 0:
       - obligation = shortfall × (season_catches[agent_id] / total_season_catch)
       - proportional_debts[agent_id] = obligation
   - Reset season_catches and season_deposits for next season

### Config Activation

Update state/config.json["norms"] to REPLACE existing norm:
```json
[{
  "type": "catch_limit_with_seasonal_reserve",
  "id": "round_4_limit",
  "max_kg_per_trip": 6.0,
  "reserve_deposit_percent": 0.10,
  "min_stock_percent_remaining": 0.10,
  "season_end_reserve_percent": 0.12,
  "ban_rounds": 1
}]
```

### Institution Update

Update state/institution.json["norm_types"]:
```json
{
  "catch_limit_with_seasonal_reserve": {
    "description": "Enforces 6kg per-trip limit, 90% collective stock limit, 10% reserve deposit per catch, and 12% season-end reserve target with proportional shortfall redistribution",
    "owner": "norms/catch_limit_with_seasonal_reserve.py"
  }
}
```

### Fluent for Norm Active

Update state/fluents.json:
- End fluent: norm_active, args={"type": "tiered_catch_limit_with_forfeiture"}, round=4
- New fluent: norm_active, args={"type": "catch_limit_with_seasonal_reserve"}, holder=community, round=4

### Fluent Schema Update

Add to state/fluents_schema.md:
- `seasonal_reserve_active` - Indicates a seasonal reserve accumulation period is in effect
- `reserve_deposit` - Records a fisher's contribution to shared reserve
- `proportional_debt` - Indicates a fisher owes additional deposit from season-end shortfall

---

## Verification Matrix

| Requirement | Shape | Owner | Verification |
|-------------|-------|-------|--------------|
| 6kg per-trip limit | catch_constraint | norms/catch_limit_with_seasonal_reserve.py | tests/norm_checks/test_round_4_reserve.py |
| 90% collective stock rule | collective_constraint | norms/catch_limit_with_seasonal_reserve.py | tests/norm_checks/test_round_4_reserve.py |
| 10% reserve deposit | state_tracking | norms/catch_limit_with_seasonal_reserve.py | tests/norm_checks/test_round_4_reserve.py |
| 12% season-end reserve target | season_end_check | norms/catch_limit_with_seasonal_reserve.py | tests/norm_checks/test_round_4_reserve.py |
| Proportional shortfall redistribution | debt_assignment | norms/catch_limit_with_seasonal_reserve.py | tests/norm_checks/test_round_4_reserve.py |
| Ban for violations/non-payment | eligibility_check | norms/catch_limit_with_seasonal_reserve.py | tests/norm_checks/test_round_4_reserve.py |

---

```json
{
  "requirements": [
    {
      "id": 1,
      "description": "Fixed 6kg per-trip catch limit with forfeiture of excess",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_seasonal_reserve.py",
      "parametric": false
    },
    {
      "id": 2,
      "description": "90% collective stock rule (leave 10% untouched)",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_seasonal_reserve.py",
      "parametric": false
    },
    {
      "id": 3,
      "description": "10% deposit from every catch into shared reserve",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_seasonal_reserve.py",
      "parametric": false
    },
    {
      "id": 4,
      "description": "Reserve must reach 12% of lake's final stock at season end",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_seasonal_reserve.py",
      "parametric": false
    },
    {
      "id": 5,
      "description": "Proportional shortfall redistribution among fishers",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_seasonal_reserve.py",
      "parametric": false
    },
    {
      "id": 6,
      "description": "Ban for limit violations or non-payment of obligations",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_seasonal_reserve.py",
      "parametric": false
    },
    {
      "id": 7,
      "description": "Record-keeper logs lake stock",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Stock automatically tracked; no manual logging step exists"
    },
    {
      "id": 8,
      "description": "Record-keeper updates ledger",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Ledger updates are automatic system processes"
    },
    {
      "id": 9,
      "description": "Council verifies totals",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Verification is deterministic arithmetic, no judgment needed"
    },
    {
      "id": 10,
      "description": "Seven-day recording window for additional deposits",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Simulation uses discrete rounds, not continuous time/days"
    },
    {
      "id": 11,
      "description": "Council enforces ban and seizes fish",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Enforcement is automatic; no discretionary decisions needed"
    }
  ],
  "actions_added": [],
  "norms_added": ["catch_limit_with_seasonal_reserve"],
  "norms_replaced": ["tiered_catch_limit_with_forfeiture"]
}
```
