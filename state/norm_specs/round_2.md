# Round 2 Norm Specification

## Source Norm

**Policy:** No fisher may take more than 15% of the lake's current stock on a trip, capped at 20kg; a violation triggers a 5kg tax from the next catch and loss of permission for the following trip.

**Operationalization:**
1. After each trip, the fisher who returns records their catch and current reserve in the shared ledger.
2. The designated ledger keeper immediately updates the lake stock by subtracting that catch from the previous total and posts the new stock for all to see.
3. At the end of each month a volunteer audit team of three community members compares the ledger entries to the lake stock; if a fisher's catch exceeds the 15%/20kg limit, the team flags the violation, the fisher must set aside 5kg from the next catch and deposit it into the community tax box before logging the trip, and that fisher is denied permission for the following trip.
4. The 5kg tax is recorded as a separate line in the ledger, added to the communal fund, and used for lake maintenance, net subsidies, or emergency food support.
5. All fishers are required to maintain at least 1kg of reserve to stay able to fish; if reserves drop below zero fishing ceases until the reserve is replenished.

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
- catch_limit_with_forfeiture (from Round 1) — to be REPLACED, not supplemented

---

## Requirement Analysis

### Requirement 1: Catch Limit Enforcement (15% or 20kg)

**Clarity:** CLEAR

- **Purpose:** Prevent any single fisher from taking too large a share of the lake's stock
- **Actor:** System/audit team (deterministic enforcement)
- **Action/Decision:** Calculate limit as min(15% of current stock, 20kg), detect violations
- **Existing action or new action:** Norm plugin (norms/*.py)
- **Inputs:** Current stock level, actual catch amount
- **Outputs:** Violation flag, kept amount (no immediate forfeiture — different from Round 1!)
- **State read:** runtime["stock_kg"]
- **State changed:** runtime["norms"][key]["violations"][agent_id] = True
- **Timing / Frequency:** Every harvest action, per agent
- **Participation:** All fishers
- **Gate:** N/A (always active)
- **Institutional consequence:** Violation recorded, triggers tax on next catch and ban
- **Agent-visible information:** Note explaining violation recorded
- **Verification:** Test catch at exactly 15%, at 20kg, above both limits, below both limits

**Key difference from Round 1:** The catch itself is NOT reduced in the violating round. The full catch is kept, but a violation is recorded.

### Requirement 2: Tax on Next Catch (5kg)

**Clarity:** CLEAR

- **Purpose:** Penalize limit violations through a future tax
- **Actor:** System (deterministic enforcement)
- **Action/Decision:** Deduct 5kg from next catch if violation recorded
- **Existing action or new action:** Norm plugin (norms/*.py)
- **Inputs:** Agent's violation history, current catch amount
- **Outputs:** Adjusted kept amount, tax amount
- **State read:** runtime["norms"][key]["violations"][agent_id]
- **State changed:** runtime["norms"][key]["tax_paid"][agent_id], runtime["norms"][key]["community_fund"]
- **Timing / Frequency:** Every harvest action, per agent (after violation detection)
- **Participation:** Fishers with prior violations
- **Gate:** N/A
- **Institutional consequence:** 5kg deducted from catch, added to communal fund
- **Agent-visible information:** Note explaining tax deduction
- **Verification:** Test fisher with prior violation has 5kg deducted; fisher without violation pays no tax

### Requirement 3: Loss of Permission for Following Trip (Ban)

**Clarity:** CLEAR

- **Purpose:** Prevent fishers from fishing the round immediately following a violation
- **Actor:** System (deterministic enforcement)
- **Action/Decision:** Check if agent has unaddressed violation, skip next round
- **Existing action or new action:** Norm plugin (norms/*.py) via is_eligible()
- **Inputs:** Agent ID, violation history
- **Outputs:** Eligibility boolean
- **State read:** runtime["norms"][key]["pending_ban"][agent_id]
- **State changed:** None (read-only check)
- **Timing / Frequency:** Every harvest action, before each agent's turn
- **Participation:** Fishers with violations from previous round
- **Gate:** N/A
- **Institutional consequence:** Banned agents skip fishing (no LLM call)
- **Agent-visible information:** Constraints line noting ban status
- **Verification:** Test fisher banned after violation, can fish again after ban round

### Requirement 4: Community Tax Box / Communal Fund

**Clarity:** CLEAR

- **Purpose:** Collect tax revenue for community benefit
- **Actor:** System (deterministic tracking)
- **Action/Decision:** Accumulate all tax payments into community fund
- **Existing action or new action:** Norm plugin (norms/*.py)
- **Inputs:** Tax payments from each fisher
- **Outputs:** Updated community fund total
- **State read:** runtime["norms"][key]["community_fund"]
- **State changed:** runtime["norms"][key]["community_fund"] (incremented by tax payments)
- **Timing / Frequency:** Every harvest action, when tax is paid
- **Participation:** N/A (system process)
- **Gate:** N/A
- **Institutional consequence:** Community fund grows, visible to all
- **Agent-visible information:** Community fund balance in constraints
- **Verification:** Test fund increases by 5kg per taxed catch

### Requirement 5: Minimum 1kg Reserve Requirement

**Clarity:** CLEAR

- **Purpose:** Ensure fishers maintain sufficient reserves to survive
- **Actor:** System (deterministic check)
- **Action/Decision:** Check if payoff < 1.0, ban from fishing if true
- **Existing action or new action:** Norm plugin (norms/*.py) via is_eligible()
- **Inputs:** Agent's current payoff/reserve
- **Outputs:** Eligibility boolean
- **State read:** runtime["payoff"][agent_id]
- **State changed:** None (read-only check)
- **Timing / Frequency:** Every harvest action, before each agent's turn
- **Participation:** Fishers with reserves below 1kg
- **Gate:** N/A
- **Institutional consequence:** Low-reserve agents skip fishing until reserves replenished
- **Agent-visible information:** Constraints line noting reserve requirement
- **Verification:** Test fisher with 0.5kg reserve cannot fish; fisher with 1.5kg can fish

### Requirement 6: Recording Catch and Reserve in Ledger

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The norm asks fishers to "record their catch and current reserve in the shared ledger." In the simulation, the catch is automatically computed by physics and recorded in round results. The reserve (payoff) is already tracked in runtime. There is no separate "recording" step that fishers perform — the system tracks this automatically. The norm seems to describe a manual logging process that doesn't exist in the current architecture.

### Requirement 7: Designated Ledger Keeper

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The ledger keeper's role is to "update the lake stock by subtracting that catch." Stock updates are handled automatically by the harvest action and physics. This is a ceremonial role for a deterministic process.

### Requirement 8: Volunteer Audit Team

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The audit team "compares the ledger entries to the lake stock" and "flags the violation." Violation detection is purely arithmetic (catch > limit) and can be done deterministically. There's no judgment involved that requires three community members. This is a ceremonial process for what the norm plugin calculates automatically.

### Requirement 9: Tax Use (Lake Maintenance, Net Subsidies, Emergency Food)

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The norm mentions uses for the community fund but doesn't specify any mechanical consequences or decisions tied to these uses. The fund accumulation is tracked, but the "use" is narrative only without simulation mechanics.

---

## Design Decisions

### Parametric vs. Structural

Requirements 1-5 route to a single new norm plugin: **catch_limit_with_tax_and_ban**

This norm type will:
- Calculate limit = min(stock * 0.15, 20) and detect violations (no immediate forfeiture)
- Record violations for future tax application
- Deduct 5kg tax from next catch after a violation
- Track community fund total
- Enforce one-round ban after violation
- Check minimum 1kg reserve requirement

Requirements 6-9 are not implemented due to being technically unrealizable (they describe ceremonial/manual processes that don't add enforceable mechanics in the simulation).

### Why Replace Round 1 Norm?

Round 1's norm (catch_limit_with_forfeiture) is **incompatible** with Round 2's policy:
- Round 1: Immediate forfeiture of excess catch
- Round 2: No forfeiture, instead tax on next catch + ban

These are mutually exclusive enforcement mechanisms for the same catch limit rule. Round 2's config should REPLACE the Round 1 norm, not supplement it.

### Why No New Actions?

All requirements are deterministic calculations that don't require agent judgment:
- Catch limit calculation = arithmetic
- Tax deduction = arithmetic
- Ban eligibility = comparison
- Reserve check = comparison

None involve discretionary decisions by agents.

---

## Implementation Plan

### New Norm Type: catch_limit_with_tax_and_ban

**File:** norms/catch_limit_with_tax_and_ban.py
**Type name:** catch_limit_with_tax_and_ban
**Parameters:**
- percent_limit: 0.15 (15%)
- kg_limit: 20.0 (20kg)
- tax_kg: 5.0 (5kg tax)
- min_reserve_kg: 1.0 (minimum reserve to fish)

**State Schema:**
```json
{
  "violations": {
    "agent_id": round_number_of_violation
  },
  "tax_paid": {
    "agent_id": total_tax_paid
  },
  "community_fund": total_kg,
  "banned": {
    "agent_id": ban_until_round
  }
}
```

**Behavior:**

1. **is_eligible(agent_id):**
   - Check if payoff[agent_id] < min_reserve_kg → False
   - Check if banned[agent_id] > current_round → False
   - Return True otherwise

2. **describe(agent_id):**
   - If banned: "You are banned from fishing until round X."
   - If low reserve: "You need at least 1kg reserve to fish."
   - Show current limit: "Catch limit is min(15% of stock, 20kg)."
   - Show community fund: "Community fund: X kg."
   - If has violation: "You have a pending 5kg tax on your next catch."

3. **evaluate(agent_id, raw_kg):**
   - Step 1: Apply tax if agent has prior violation
     - If violations[agent_id] exists and < current_round:
       - tax = min(tax_kg, raw_kg)  // Can't tax more than caught
       - kept_after_tax = raw_kg - tax
       - Record tax payment
       - Add to community_fund
       - Clear violation flag
   - Step 2: Check current catch against limit
     - limit = min(stock * percent_limit, kg_limit)
     - If kept_after_tax > limit:
       - Record violation at current round
       - Record ban for next round (current_round + 1)
       - Return violation decision (but keep full catch — no forfeiture!)
     - Else:
       - Return allow decision

4. **on_round_end():**
   - No stock override needed (no forfeiture)
   - Persist community fund total

### Config Activation

Update state/config.json["norms"] to REPLACE existing norm:
```json
[{
  "type": "catch_limit_with_tax_and_ban",
  "id": "round_2_limit",
  "percent_limit": 0.15,
  "kg_limit": 20.0,
  "tax_kg": 5.0,
  "min_reserve_kg": 1.0
}]
```

### Institution Update

Update state/institution.json["norm_types"]:
```json
{
  "catch_limit_with_tax_and_ban": {
    "description": "Enforces catch limit (15% or 20kg) with 5kg tax on next catch and one-trip ban for violations, plus minimum reserve requirement",
    "owner": "norms/catch_limit_with_tax_and_ban.py"
  }
}
```

### Fluent for Norm Active

Update state/fluents.json (end any existing norm_active for catch_limit_with_forfeiture, add new for catch_limit_with_tax_and_ban):
- End fluent: norm_active, args={"type": "catch_limit_with_forfeiture"}, round=2
- New fluent: norm_active, args={"type": "catch_limit_with_tax_and_ban"}, holder=community, round=2

### Fluent Schema Update

Add to state/fluents_schema.md:
- `tax_pending` - Indicates a fisher has a pending tax obligation from a prior violation
- `banned` - Indicates a fisher is temporarily banned from fishing

---

## Verification Matrix

| Requirement | Shape | Owner | Verification |
|-------------|-------|-------|--------------|
| Catch limit detection (15% or 20kg) | catch_violation_detection | norms/catch_limit_with_tax_and_ban.py | tests/norm_checks/test_round_2_tax_ban.py |
| Tax on next catch (5kg) | tax_deduction | norms/catch_limit_with_tax_and_ban.py | tests/norm_checks/test_round_2_tax_ban.py |
| Ban after violation | eligibility_check | norms/catch_limit_with_tax_and_ban.py | tests/norm_checks/test_round_2_tax_ban.py |
| Community fund tracking | state_tracking | norms/catch_limit_with_tax_and_ban.py | tests/norm_checks/test_round_2_tax_ban.py |
| Minimum reserve check (1kg) | eligibility_check | norms/catch_limit_with_tax_and_ban.py | tests/norm_checks/test_round_2_tax_ban.py |

---

```json
{
  "requirements": [
    {
      "id": 1,
      "description": "Catch limit enforcement: min(15% of stock, 20kg) — violation detection only, no forfeiture",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_tax_and_ban.py",
      "parametric": false
    },
    {
      "id": 2,
      "description": "5kg tax on next catch after violation",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_tax_and_ban.py",
      "parametric": false
    },
    {
      "id": 3,
      "description": "One-trip ban after violation",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_tax_and_ban.py",
      "parametric": false
    },
    {
      "id": 4,
      "description": "Community tax box / communal fund tracking",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_tax_and_ban.py",
      "parametric": false
    },
    {
      "id": 5,
      "description": "Minimum 1kg reserve requirement",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_tax_and_ban.py",
      "parametric": false
    },
    {
      "id": 6,
      "description": "Recording catch and reserve in ledger",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Catch and reserve automatically tracked; no separate recording step exists"
    },
    {
      "id": 7,
      "description": "Designated ledger keeper role",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Stock updates are automatic, no manual keeper needed"
    },
    {
      "id": 8,
      "description": "Volunteer audit team",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Violation detection is deterministic arithmetic, no judgment needed"
    },
    {
      "id": 9,
      "description": "Tax use for lake maintenance/net subsidies/emergency food",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "No simulation mechanics for fund expenditure; tracking only"
    }
  ],
  "actions_added": [],
  "norms_added": ["catch_limit_with_tax_and_ban"],
  "norms_replaced": ["catch_limit_with_forfeiture"]
}
```
