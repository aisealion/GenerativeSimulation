# Round 5 Norm Specification

## Source Norm

**Policy:** Each fisher may take a maximum of 5 kg per trip, must leave at least 15% of the lake's current stock untouched, and 12% of every catch each season will be deposited into a shared reserve for future generations.

**Operationalization:**
1. A trip starts when a fisher departs the dock or boat for fishing and ends when the fisher returns to the dock/boat or takes a break longer than 30 minutes. The fisher records the total catch for that trip in the shared ledger upon return.
2. After each trip the observer, elected as the Lake Monitor each season, measures the lake stock and verifies the 15% untouched rule against the post-trip stock; if the fisher's catch exceeds 5 kg or the remaining stock falls below 15%, the excess fish are returned to the lake and a penalty of one extra 1 kg trip is added to the ledger.
3. The 12% of the season's total catch is calculated at the end of the season, added to the reserve ledger, and the corresponding kilograms are physically placed in a communal reserve container at the dock.
4. The Lake Monitor guards the container, ensures the ledger matches the physical stock, and reports any discrepancies at the monthly meeting.
5. No fisher may take from the reserve until the fishing council adopts a rule for access by majority vote.

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
- catch_limit_with_seasonal_reserve (from Round 4) — to be REPLACED, not supplemented

---

## Requirement Analysis

### Requirement 1: Fixed 5kg Per-Trip Catch Limit

**Clarity:** CLEAR

- **Purpose:** Establish a hard cap on individual catch per trip
- **Actor:** System/Lake Monitor (deterministic enforcement)
- **Action/Decision:** Enforce that no fisher keeps more than 5kg from any single trip
- **Existing action or new action:** Norm plugin (norms/*.py)
- **Inputs:** Actual catch amount (raw_kg)
- **Outputs:** Kept amount (max 5kg), forfeited amount (excess over 5kg)
- **State read:** runtime["norms"][key]
- **State changed:** runtime["norms"][key]["forfeited_to_reserve"][agent_id]
- **Timing / Frequency:** Every harvest action, per agent
- **Participation:** All fishers
- **Gate:** N/A (always active)
- **Institutional consequence:** Excess over 5kg forfeited to communal reserve, violation recorded
- **Agent-visible information:** Note explaining 5kg limit and forfeiture
- **Verification:** Test catches at 5kg, below 5kg, above 5kg

**Key difference from Round 4:** Round 4 had 6kg limit. Round 5 reduces to 5kg.

### Requirement 2: Leave 15% of Lake Stock Untouched (85% Rule)

**Clarity:** CLEAR

- **Purpose:** Ensure collective harvest never exceeds 85% of current stock, preserving minimum 15%
- **Actor:** System/Lake Monitor (deterministic enforcement)
- **Action/Decision:** Calculate max_take = 0.85 × current_stock; reject or limit catches that would violate this
- **Existing action or new action:** Norm plugin (norms/*.py)
- **Inputs:** Current stock level, cumulative harvest this round
- **Outputs:** Eligibility or adjusted catch limits
- **State read:** runtime["stock_kg"], runtime["norms"][key] scratch data
- **State changed:** runtime["norms"][key]["violations"]
- **Timing / Frequency:** Every harvest action, per agent
- **Participation:** All fishers
- **Gate:** N/A
- **Institutional consequence:** Agents violating the 85% rule forfeit excess and receive penalty trip
- **Agent-visible information:** Constraint showing remaining collective allowance
- **Verification:** Test scenario where cumulative catches approach 85% of stock

**Key difference from Round 4:** Round 4 had 90% rule (leave 10%). Round 5 is stricter: 85% rule (leave 15%).

### Requirement 3: Penalty Trip for Violations (1kg Extra Trip)

**Clarity:** CLEAR

- **Purpose:** Penalize non-compliance by adding mandatory low-yield trip to fisher's record
- **Actor:** System/Lake Monitor (deterministic enforcement)
- **Action/Decision:** If fisher exceeds 5kg limit OR violates 15% stock rule → add penalty trip (1kg) to ledger
- **Existing action or new action:** Norm plugin (norms/*.py)
- **Inputs:** Agent ID, violation status, current penalty trip count
- **Outputs:** Updated penalty trip tracking
- **State read:** runtime["norms"][key]["violations"][agent_id]
- **State changed:** runtime["norms"][key]["penalty_trips"][agent_id] (count), runtime["norms"][key]["penalty_trip_kg"][agent_id] (total kg owed)
- **Timing / Frequency:** Every harvest action where violation occurs
- **Participation:** Fishers who violate limits
- **Gate:** N/A
- **Institutional consequence:** Penalty trips accumulate; fisher must complete them before normal fishing resumes
- **Agent-visible information:** Note explaining penalty trip added and current penalty balance
- **Verification:** Test penalty trip added after limit violation, after stock rule violation

**Key difference from Round 4:** Round 4 used a ban (skip next round). Round 5 uses penalty trips (mandatory 1kg trips added to ledger).

### Requirement 4: Penalty Trip Enforcement (Mandatory 1kg Trips)

**Clarity:** CLEAR

- **Purpose:** Ensure penalty trips are actually executed - fisher must take 1kg trips until penalties cleared
- **Actor:** System/Lake Monitor (deterministic enforcement)
- **Action/Decision:** If fisher has pending penalty trips, their next trip(s) are limited to exactly 1kg (the penalty trip amount) until all penalties are satisfied
- **Existing action or new action:** Norm plugin (norms/*.py) via is_eligible() and evaluate()
- **Inputs:** Agent ID, pending penalty trip count
- **Outputs:** Eligibility status, penalty-adjusted catch limits
- **State read:** runtime["norms"][key]["penalty_trips"][agent_id]
- **State changed:** runtime["norms"][key]["penalty_trips"][agent_id] (decrement as served), runtime["norms"][key]["penalty_trip_kg"][agent_id]
- **Timing / Frequency:** Every harvest action, before and during agent processing
- **Participation:** Fishers with pending penalty trips
- **Gate:** N/A (penalty trips are mandatory but don't block eligibility - they override the catch amount)
- **Institutional consequence:** Fishers with penalties get only 1kg per trip until penalties cleared
- **Agent-visible information:** Constraints line showing X penalty trips remaining
- **Verification:** Test that penalty trips force 1kg limit, test that multiple penalties require multiple trips

### Requirement 5: 12% Deposit Into Shared Reserve

**Clarity:** CLEAR

- **Purpose:** Build communal reserve fund from each catch for collective benefit/future generations
- **Actor:** System/Lake Monitor (deterministic enforcement)
- **Action/Decision:** Deduct 12% from every kept catch, add to shared reserve
- **Existing action or new action:** Norm plugin (norms/*.py)
- **Inputs:** Kept catch amount after limit enforcement
- **Outputs:** Final payoff (88% of kept), reserve deposit (12% of kept)
- **State read:** runtime["norms"][key]["shared_reserve"]
- **State changed:** runtime["norms"][key]["shared_reserve"], runtime["norms"][key]["season_deposits"][agent_id]
- **Timing / Frequency:** Every harvest action, per agent
- **Participation:** All fishers
- **Gate:** N/A
- **Institutional consequence:** Fishers receive 88% of their allowed catch; 12% goes to community reserve
- **Agent-visible information:** Note showing gross catch, deposit amount, net received
- **Verification:** Test that 12% of every kept catch goes to reserve

**Key difference from Round 4:** Round 4 had 10% deposit. Round 5 increases to 12%.

### Requirement 6: Reserve Is Locked (No Access Until Council Vote)

**Clarity:** CLEAR

- **Purpose:** Preserve reserve for future generations; prevent immediate consumption
- **Actor:** System/council (enforced by norm until council action)
- **Action/Decision:** Reserve contributions are one-way; no fisher can withdraw from reserve
- **Existing action or new action:** Norm plugin (norms/*.py) - no withdrawal mechanism provided
- **Inputs:** N/A (this is an absence of functionality)
- **Outputs:** N/A
- **State read:** runtime["norms"][key]["shared_reserve"]
- **State changed:** None (reserve only accumulates)
- **Timing / Frequency:** Ongoing
- **Participation:** All fishers (restricted from access)
- **Gate:** N/A
- **Institutional consequence:** Reserve accumulates indefinitely until council adopts access rule
- **Agent-visible information:** Note that reserve is locked pending council vote
- **Verification:** Verify no mechanism exists to reduce shared_reserve except forfeiture deposits

### Requirement 7: Trip Definition (Start/End)

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The norm defines a trip as starting when a fisher "departs the dock or boat" and ending on "return to the dock/boat or break longer than 30 minutes." The simulation does not model continuous time or trip durations. Each harvest action represents a complete fishing decision within a round. The 30-minute break concept has no mapping to the discrete round-based simulation structure.

### Requirement 8: Fisher Records Catch in Ledger

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The norm describes fishers manually recording catches in a shared ledger. In the simulation, catches are automatically computed by physics and tracked in the runtime state. There is no manual logging step that fishers perform.

### Requirement 9: Lake Monitor Measures Stock and Verifies 15% Rule

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The Lake Monitor role is described as measuring stock and verifying the 15% rule. These are deterministic arithmetic operations (checking if catch ≤ 5kg and if remaining_stock ≥ 15% of original) that don't require agent judgment. The monitor is a ceremonial role for algorithmic processes handled by the norm plugin.

### Requirement 10: Excess Fish Returned to Lake

**Clarity:** CLEAR (Implemented as part of Requirements 1-2)

**Rationale:** The forfeiture of excess fish is already covered in Requirements 1 and 2. When a fisher exceeds limits, the excess is returned to the lake (conceptually) and added to the shared reserve (operationally).

### Requirement 11: Lake Monitor Guards Container and Verifies Ledger

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The Lake Monitor's role in guarding the container and verifying ledger matches physical stock describes deterministic validation. The norm plugin ensures ledger consistency automatically; no separate verification step is needed.

### Requirement 12: Monthly Meeting Discrepancy Reports

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The norm mentions monthly meetings for discrepancy reports. The simulation operates in rounds without a continuous timeline that maps to months or meetings. Discrepancies cannot occur because the system is deterministic and self-consistent.

### Requirement 13: Council Access Rule by Majority Vote

**Clarity:** CLEAR (Future implementation, not current)

**Rationale:** The norm states that no fisher may take from the reserve "until the fishing council adopts a rule for access by majority vote." This is a conditional future state - currently there is no such rule, so the reserve remains locked. The current implementation ensures the reserve is locked; enabling access would require a future council action (new proposal/vote mechanism).

---

## Design Decisions

### Parametric vs. Structural

Requirements 1-6 route to a single new norm plugin: **catch_limit_with_penalty_trips**

This norm type will:
- Enforce a fixed 5kg per-trip limit with forfeiture of excess
- Track cumulative harvest against 85% of stock limit (15% untouched)
- Deduct 12% from every catch into a shared reserve
- Add penalty trips (1kg mandatory trips) for limit violations
- Enforce penalty trips by limiting affected fishers to 1kg per trip until penalties cleared
- Keep reserve locked (no withdrawal mechanism)

Requirements 7-12 are not implemented due to being technically unrealizable (they describe ceremonial/manual processes or continuous-time concepts that don't add enforceable mechanics in the simulation).

Requirement 13 is satisfied by the absence of withdrawal functionality - the reserve remains locked until a future mechanism is added.

### Why Replace Round 4 Norm?

Round 4's norm (catch_limit_with_seasonal_reserve) is **incompatible** with Round 5's policy:
- Round 4: 6kg limit, 90% collective rule, 10% deposit, 12% season-end target, proportional shortfall redistribution, ban for violations
- Round 5: 5kg limit, 85% collective rule, 12% deposit, NO season-end target, penalty trips for violations (not bans), reserve locked

These are mutually exclusive enforcement mechanisms. Round 5's config should REPLACE the Round 4 norm, not supplement it.

### Key Design Challenge: Penalty Trip Mechanism

The penalty trip concept requires careful implementation:

1. **Recording Penalties:** When a violation occurs, increment penalty_trip_count and penalty_trip_kg_owed (by 1kg per penalty).

2. **Serving Penalties:** When a fisher with pending penalties fishes, their catch is limited to exactly 1kg (the penalty trip amount), regardless of their effort choice. The 1kg goes to their payoff (like a normal catch), and one penalty is marked as served.

3. **Penalty vs Normal Fishing:** A fisher with penalties fishes "normally" but only receives 1kg per trip. The 12% reserve deposit still applies to the 1kg.

4. **Multiple Penalties:** If a fisher has N penalties, they must take N trips at 1kg each. After all penalties are served, they return to normal fishing limits.

**Implementation approach:**
- Track penalty_trips_pending[agent_id] = count of unserved penalties
- In is_eligible(): Still eligible (penalties don't ban, they restrict)
- In describe(): Show "You have X penalty trips pending; your next trip is limited to 1kg"
- In evaluate(): If penalties pending > 0:
  - Override the effective limit to 1kg
  - Process as normal 1kg trip (with 12% deposit)
  - Decrement penalty_trips_pending
  - Mark this as a penalty trip in the note

### Seasonal vs Continuous Reserve

Round 4 had a season-end check with proportional redistribution. Round 5 has no season-end requirement - the reserve simply accumulates continuously. The 12% deposit happens every catch, and the reserve grows without target or redistribution.

### Why No New Actions?

All realizable requirements are deterministic calculations that don't require agent judgment:
- 5kg limit check = arithmetic comparison
- 15% stock rule = running sum comparison
- 12% deposit = arithmetic percentage
- Penalty trip tracking = counter increment/decrement
- Penalty enforcement = limit override
- Reserve lock = absence of withdrawal code

None involve discretionary decisions by agents.

---

## Implementation Plan

### New Norm Type: catch_limit_with_penalty_trips

**File:** norms/catch_limit_with_penalty_trips.py
**Type name:** catch_limit_with_penalty_trips
**Parameters:**
- max_kg_per_trip: 5.0 (5kg hard cap)
- reserve_deposit_percent: 0.12 (12% to reserve)
- min_stock_percent_remaining: 0.15 (must leave 15% = can take 85%)
- penalty_trip_kg: 1.0 (each penalty trip is 1kg)

**State Schema:**
```json
{
  "shared_reserve": total_kg_in_reserve,
  "season_deposits": {
    "agent_id": total_deposited_this_season
  },
  "penalty_trips_pending": {
    "agent_id": count_of_unserved_penalties
  },
  "penalty_trip_kg_owed": {
    "agent_id": total_kg_in_pending_penalties
  },
  "violations": {
    "agent_id": round_number_of_violation
  },
  "round_cumulative_harvest": kg_taken_this_round_so_far,
  "max_allowed_this_round": 0.85 * stock_at_round_start
}
```

**Behavior:**

1. **is_eligible(agent_id):**
   - Check if collective cap reached → False
   - Return True otherwise (even with penalties - they restrict, don't ban)

2. **describe(agent_id):**
   - Show 5kg per-trip limit
   - Show collective availability: (max_allowed_this_round - round_cumulative_harvest) remaining
   - Show shared reserve balance
   - Show 12% deposit requirement
   - If has penalty trips pending: "You have X penalty trip(s) pending. Your next trip is limited to 1kg."

3. **evaluate(agent_id, raw_kg):**
   - Step 1: Check for pending penalty trips
     - If penalty_trips_pending[agent_id] > 0:
       - This is a penalty trip - limit to exactly 1kg
       - kept_before_reserve = 1.0
       - Decrement penalty_trips_pending
       - Decrement penalty_trip_kg_owed by 1.0
       - Mark as penalty trip in note
     - Else (no penalties):
       - Step 2: Check collective availability
         - remaining_collective = max_allowed_this_round - round_cumulative_harvest
         - if remaining_collective <= 0: return reject (collective cap reached)
       - Step 3: Calculate effective limit
         - effective_limit = min(5.0, remaining_collective)
       - Step 4: Check for violation
         - if raw_kg > effective_limit:
           - kept_before_reserve = effective_limit
           - forfeited = raw_kg - effective_limit
           - Add forfeited to shared_reserve
           - Record violation
           - Add 1 penalty trip (increment penalty_trips_pending, penalty_trip_kg_owed += 1.0)
           - violation_occurred = True
         - else:
           - kept_before_reserve = raw_kg
   - Step 5: Apply 12% reserve deposit
     - deposit = kept_before_reserve × 0.12
     - final_kept = kept_before_reserve - deposit
     - Add deposit to shared_reserve
     - Update season_deposits[agent_id] += deposit
   - Step 6: Update cumulative harvest
     - round_cumulative_harvest += kept_before_reserve
   - Step 7: Build note
     - Include whether this was a penalty trip
     - Include gross catch, forfeited amount (if any), deposit amount, penalties added/served

4. **on_round_start():**
   - Reset round_cumulative_harvest = 0
   - Set max_allowed_this_round = 0.85 × context.stock_before
   - Clear round-specific tracking

5. **on_round_end():**
   - No season-end calculations (reserve just accumulates)
   - Reset season_deposits for next season if tracking seasonally

### Config Activation

Update state/config.json["norms"] to REPLACE existing norm:
```json
[{
  "type": "catch_limit_with_penalty_trips",
  "id": "round_5_limit",
  "max_kg_per_trip": 5.0,
  "reserve_deposit_percent": 0.12,
  "min_stock_percent_remaining": 0.15,
  "penalty_trip_kg": 1.0
}]
```

### Institution Update

Update state/institution.json["norm_types"]:
```json
{
  "catch_limit_with_penalty_trips": {
    "description": "Enforces 5kg per-trip limit, 85% collective stock limit, 12% reserve deposit per catch, and 1kg penalty trips for violations",
    "owner": "norms/catch_limit_with_penalty_trips.py"
  }
}
```

### Fluent for Norm Active

Update state/fluents.json:
- End fluent: norm_active, args={"type": "catch_limit_with_seasonal_reserve"}, round=5
- New fluent: norm_active, args={"type": "catch_limit_with_penalty_trips"}, holder=community, round=5

### Fluent Schema Update

Add to state/fluents_schema.md:
- `penalty_trip_assigned` - Indicates a fisher has been assigned a penalty trip for violating limits
- `penalty_trip_served` - Indicates a fisher has served/completed a penalty trip

---

## Verification Matrix

| Requirement | Shape | Owner | Verification |
|-------------|-------|-------|--------------|
| 5kg per-trip limit | catch_constraint | norms/catch_limit_with_penalty_trips.py | tests/norm_checks/test_round_5_penalty.py |
| 85% collective stock rule | collective_constraint | norms/catch_limit_with_penalty_trips.py | tests/norm_checks/test_round_5_penalty.py |
| Penalty trip assignment | penalty_tracking | norms/catch_limit_with_penalty_trips.py | tests/norm_checks/test_round_5_penalty.py |
| Penalty trip enforcement | penalty_enforcement | norms/catch_limit_with_penalty_trips.py | tests/norm_checks/test_round_5_penalty.py |
| 12% reserve deposit | state_tracking | norms/catch_limit_with_penalty_trips.py | tests/norm_checks/test_round_5_penalty.py |
| Reserve locked | absence_of_mechanism | norms/catch_limit_with_penalty_trips.py | tests/norm_checks/test_round_5_penalty.py |

---

```json
{
  "requirements": [
    {
      "id": 1,
      "description": "Fixed 5kg per-trip catch limit with forfeiture of excess",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_penalty_trips.py",
      "parametric": false
    },
    {
      "id": 2,
      "description": "85% collective stock rule (leave 15% untouched)",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_penalty_trips.py",
      "parametric": false
    },
    {
      "id": 3,
      "description": "Penalty trip assignment for violations (1kg extra trip added to ledger)",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_penalty_trips.py",
      "parametric": false
    },
    {
      "id": 4,
      "description": "Penalty trip enforcement (mandatory 1kg trips until penalties cleared)",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_penalty_trips.py",
      "parametric": false
    },
    {
      "id": 5,
      "description": "12% deposit from every catch into shared reserve",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_penalty_trips.py",
      "parametric": false
    },
    {
      "id": 6,
      "description": "Reserve is locked (no access until council adopts rule)",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_penalty_trips.py",
      "parametric": false
    },
    {
      "id": 7,
      "description": "Trip definition (start/end timing)",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Simulation uses discrete rounds, not continuous time with trip durations"
    },
    {
      "id": 8,
      "description": "Fisher records catch in shared ledger",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Catch automatically recorded by system; no manual logging step exists"
    },
    {
      "id": 9,
      "description": "Lake Monitor measures stock and verifies 15% rule",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Verification is deterministic arithmetic, no judgment required"
    },
    {
      "id": 10,
      "description": "Excess fish returned to lake",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_penalty_trips.py",
      "parametric": false
    },
    {
      "id": 11,
      "description": "Lake Monitor guards container and verifies ledger",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Ledger verification is automatic, no manual step needed"
    },
    {
      "id": 12,
      "description": "Monthly meeting discrepancy reports",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Simulation uses rounds without monthly timeline; system is self-consistent"
    },
    {
      "id": 13,
      "description": "Council access rule by majority vote (future state)",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_penalty_trips.py",
      "parametric": false
    }
  ],
  "actions_added": [],
  "norms_added": ["catch_limit_with_penalty_trips"],
  "norms_replaced": ["catch_limit_with_seasonal_reserve"]
}
```
