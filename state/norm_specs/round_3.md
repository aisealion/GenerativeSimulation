# Round 3 Norm Specification

## Source Norm

**Policy:** Each fisher may take up to 25% of the lake's current stock per trip, capped at 30 kg; if reserves drop below 20 kg, the catch is limited to 12% of lake stock or 15 kg, whichever is lower. All fishers must record reserves in the shared ledger before departure, log their actual catch after the trip, return excess immediately, and any non-compliance triggers a one-trip ban enforced by the monthly rotating lake monitor.

**Operationalization:**
1. **Reserve Tracking** – Every fisher's state now contains a "reserves" field. Before each trip, the fisher writes their current reserves into the shared ledger. If no reserve is recorded or it is wrong, the fisher is flagged non-compliant, must return all fish taken that trip, and receives a one-trip ban.
2. **Catch Logging** – After a trip, the fisher logs the exact catch in the ledger. The lake monitor checks this against the allowed amount:
   * allowed = min(0.25 × lakeStock, 30 kg) if reserves ≥ 20 kg;
   * allowed = min(0.12 × lakeStock, 15 kg) if reserves < 20 kg.
   Any catch above the allowed amount is considered excess and must be returned immediately.
3. **Lake Stock Update** – The monitor subtracts the allowed catch from the current lake stock and writes the new lake stock to the ledger. The fisher's reserves are increased by the allowed catch amount.
4. **Ban Process** – If a fisher logs a catch that exceeds the allowed amount, or fails to record reserves or log the catch, the monitor records a ban in the ledger with status "Banned" and a ban period that lasts until the next trip is logged by the monitor. The ban takes effect immediately; the fisher is blocked from logging a new trip.
5. **Ban Lift** – A banned fisher must bring the excess catch to the monitor's office. The monitor logs the trip, updates the fisher's reserves, removes the "Banned" flag, and broadcasts the new lake stock and reserves. The ban is therefore lifted after the next trip is logged.
6. **Monitor Selection** – Each month, the community draws a name from a hat among fishers who have taken at least two trips in the last 30 days and are not currently banned. That fisher becomes the rotating lake monitor for the month. The monitor verifies ledger entries weekly, enforces excess returns, records bans, and broadcasts updates.
7. **Ledger Broadcast** – After every logged trip, the monitor updates the ledger and posts the new lake stock and all fishers' reserves to the community notice board (physical or digital). This keeps every fisher aware of current limits.
8. **Enforcement of Non-Compliance** – If a fisher fails to log a catch, the monitor will flag the trip as non-compliant, require the fisher to return all fish taken, and impose a one-trip ban until the catch is properly logged.
9. **Transparency** – All ledger entries, including reserves, catches, bans, and lake stock updates, are publicly visible to all fishers to ensure accountability.

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
- catch_limit_with_tax_and_ban (from Round 2) — to be REPLACED, not supplemented

---

## Requirement Analysis

### Requirement 1: Tiered Catch Limit Based on Reserves (25%/30kg or 12%/15kg)

**Clarity:** CLEAR

- **Purpose:** Create a progressive restriction system where low-reserve fishers face stricter limits
- **Actor:** System/monitor (deterministic enforcement)
- **Action/Decision:** Calculate limit based on fisher's reserve level:
  - If reserves ≥ 20 kg: limit = min(25% of stock, 30 kg)
  - If reserves < 20 kg: limit = min(12% of stock, 15 kg)
- **Existing action or new action:** Norm plugin (norms/*.py)
- **Inputs:** Current stock level, fisher's reserves (payoff), actual catch amount
- **Outputs:** Allowed amount, excess amount, violation flag
- **State read:** runtime["stock_kg"], runtime["payoff"][agent_id]
- **State changed:** runtime["norms"][key]["excess_returned"][agent_id], runtime["norms"][key]["violations"][agent_id]
- **Timing / Frequency:** Every harvest action, per agent
- **Participation:** All fishers
- **Gate:** N/A (always active)
- **Institutional consequence:** Excess catch immediately forfeited, violation recorded, ban triggered
- **Agent-visible information:** Note explaining limit calculation based on their reserve level
- **Verification:** Test both tiers: high reserves (≥20kg) get 25%/30kg limit, low reserves (<20kg) get 12%/15kg limit

**Key difference from Round 2:** Round 2 had a single catch limit. Round 3 has a TWO-TIER system based on reserve levels.

### Requirement 2: Immediate Excess Return (Forfeiture)

**Clarity:** CLEAR

- **Purpose:** Ensure fishers cannot keep more than their allowed amount
- **Actor:** System/monitor (deterministic enforcement)
- **Action/Decision:** Calculate excess = actual_catch - allowed, return excess to lake stock
- **Existing action or new action:** Norm plugin (norms/*.py)
- **Inputs:** Allowed amount (from tiered calculation), actual catch amount
- **Outputs:** Kept amount (after forfeiture), excess amount returned
- **State read:** runtime["norms"][key] violation tracking
- **State changed:** runtime["norms"][key]["excess_this_round"][agent_id] = excess_kg
- **Timing / Frequency:** Every harvest action, per agent
- **Participation:** Fishers who exceed their limit
- **Gate:** N/A
- **Institutional consequence:** Excess fish returned to communal pool (lake stock)
- **Agent-visible information:** Note explaining forfeiture amount
- **Verification:** Test that excess is correctly calculated and recorded

**Key difference from Round 2:** Round 2 allowed the full catch but taxed the NEXT catch. Round 3 requires IMMEDIATE return of excess.

### Requirement 3: Reserve-Based Eligibility and State Field

**Clarity:** CLEAR

- **Purpose:** Track reserves explicitly and make them visible to the norm system
- **Actor:** System (automatic tracking)
- **Action/Decision:** Use payoff field as "reserves" for norm calculations
- **Existing action or new action:** Norm plugin uses existing payoff field
- **Inputs:** Agent's current payoff
- **Outputs:** Reserve level classification (high ≥20kg vs low <20kg)
- **State read:** runtime["payoff"][agent_id]
- **State changed:** None (read-only, payoff already tracked)
- **Timing / Frequency:** Every harvest action
- **Participation:** All fishers
- **Gate:** N/A
- **Institutional consequence:** Determines which catch limit tier applies
- **Agent-visible information:** Current reserve level and which tier applies
- **Verification:** Test that payoff correctly reflects reserve status

### Requirement 4: Ban for Violations (One-Trip Ban)

**Clarity:** CLEAR

- **Purpose:** Penalize non-compliance by preventing next trip
- **Actor:** System/monitor (deterministic enforcement)
- **Action/Decision:** If violation detected, ban fisher for next round
- **Existing action or new action:** Norm plugin (norms/*.py) via is_eligible()
- **Inputs:** Agent ID, violation status
- **Outputs:** Eligibility boolean, ban tracking
- **State read:** runtime["norms"][key]["violations"][agent_id]
- **State changed:** runtime["norms"][key]["ban_until"][agent_id] = next_round
- **Timing / Frequency:** Every harvest action, before each agent's turn
- **Participation:** Fishers who exceeded limit or failed to log
- **Gate:** N/A
- **Institutional consequence:** Banned agents skip fishing (no LLM call)
- **Agent-visible information:** Constraints line noting ban status
- **Verification:** Test fisher banned after violation, can fish again after ban round

**Key difference from Round 2:** Similar ban mechanism but triggered by immediate forfeiture violation rather than tax-eligibility violation.

### Requirement 5: Ban Lift Process (After Monitor Logs Trip)

**Clarity:** CLEAR

- **Purpose:** Allow banned fishers to resume fishing after compliance
- **Actor:** System/monitor (deterministic process)
- **Action/Decision:** Clear ban flag after ban period expires
- **Existing action or new action:** Norm plugin (norms/*.py) via is_eligible()
- **Inputs:** Current round, ban_until round
- **Outputs:** Updated eligibility
- **State read:** runtime["norms"][key]["ban_until"][agent_id]
- **State changed:** None (ban expires automatically when current_round >= ban_until)
- **Timing / Frequency:** Every harvest action, before each agent's turn
- **Participation:** Previously banned fishers
- **Gate:** N/A
- **Institutional consequence:** Ban lifted automatically after period expires
- **Agent-visible information:** Note that ban has been lifted
- **Verification:** Test ban is lifted after one trip skipped

### Requirement 6: Reserve Recording Before Departure

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The norm asks fishers to "write their current reserves into the shared ledger" before departure. In the simulation, reserves (payoff) are automatically tracked and updated. There is no separate "recording" step that fishers perform — the system tracks this automatically. The norm describes a manual logging process that doesn't exist in the current architecture.

### Requirement 7: Catch Logging After Trip

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The norm asks fishers to "log the exact catch in the ledger" after a trip. In the simulation, the catch is automatically computed by physics and recorded in round results. There is no separate logging step that fishers perform. The norm seems to describe a manual logging process that doesn't exist in the current architecture.

### Requirement 8: Lake Monitor Selection (Rotating Monthly)

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The norm describes a "rotating lake monitor" selected monthly from eligible fishers. However, the monitor's duties (verifying ledger entries, enforcing excess returns, recording bans, broadcasting updates) are all deterministic arithmetic operations that don't require agent judgment. The monitor is a ceremonial role for processes that are algorithmically determined by the norm plugin itself.

### Requirement 9: Lake Stock Update by Monitor

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The monitor's role in "subtracting the allowed catch from the current lake stock" describes a deterministic calculation. Stock updates are handled automatically by the harvest action and physics. This is a ceremonial role for a deterministic process.

### Requirement 10: Ledger Broadcast to Community Notice Board

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The norm describes posting updates to a "community notice board (physical or digital)." In the simulation, stock levels and reserves are already visible to all agents through the runtime state and constraint descriptions. There is no separate "broadcast" mechanism needed.

### Requirement 11: Non-Compliance for Failure to Log Catch

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** Since catch logging is automatic (Requirement 7), the failure case "fails to log a catch" cannot occur in the simulation architecture. The consequence (return all fish, one-trip ban) is therefore not implementable as a meaningful rule.

### Requirement 12: Transparency (Public Ledger Visibility)

**Clarity:** CLEAR

- **Purpose:** Ensure all fishers can see current state for accountability
- **Actor:** System (information display)
- **Action/Decision:** Include relevant norm state in constraint descriptions
- **Existing action or new action:** Norm plugin via describe()
- **Inputs:** Norm state (violations, bans, lake stock)
- **Outputs:** Human-readable description for agents
- **State read:** runtime["norms"][key], runtime["stock_kg"]
- **State changed:** None (read-only)
- **Timing / Frequency:** Every harvest action
- **Participation:** All fishers
- **Gate:** N/A
- **Institutional consequence:** Agents have information needed to comply
- **Agent-visible information:** Current limits, bans, lake stock, violation history
- **Verification:** Test describe() returns comprehensive information

---

## Design Decisions

### Parametric vs. Structural

Requirements 1-5 and 12 route to a single new norm plugin: **tiered_catch_limit_with_forfeiture**

This norm type will:
- Track reserves (payoff) to determine which tier applies
- Calculate tiered limits: 25%/30kg for high reserves (≥20kg), 12%/15kg for low reserves (<20kg)
- Enforce immediate forfeiture of excess catch (unlike Round 2's tax-on-next-catch)
- Track violations and issue one-trip bans
- Handle ban expiration automatically
- Provide comprehensive transparency via describe()

Requirements 6-11 are not implemented due to being technically unrealizable (they describe ceremonial/manual processes that don't add enforceable mechanics in the simulation).

### Why Replace Round 2 Norm?

Round 2's norm (catch_limit_with_tax_and_ban) is **incompatible** with Round 3's policy:
- Round 2: Single catch limit (15% or 20kg), tax on next catch, no immediate forfeiture
- Round 3: Tiered limits based on reserves (25%/30kg vs 12%/15kg), immediate forfeiture of excess

These are mutually exclusive enforcement mechanisms. Round 3's config should REPLACE the Round 2 norm, not supplement it.

### Why No New Actions?

All realizable requirements are deterministic calculations that don't require agent judgment:
- Tiered limit calculation = arithmetic based on reserves
- Excess forfeiture = arithmetic
- Ban eligibility = comparison
- Ban expiration = comparison

None involve discretionary decisions by agents.

---

## Implementation Plan

### New Norm Type: tiered_catch_limit_with_forfeiture

**File:** norms/tiered_catch_limit_with_forfeiture.py
**Type name:** tiered_catch_limit_with_forfeiture
**Parameters:**
- high_reserve_threshold: 20.0 (kg threshold for tier classification)
- high_reserve_percent: 0.25 (25% for high reserves)
- high_reserve_kg_cap: 30.0 (30kg cap for high reserves)
- low_reserve_percent: 0.12 (12% for low reserves)
- low_reserve_kg_cap: 15.0 (15kg cap for low reserves)
- ban_rounds: 1 (one-trip ban)

**State Schema:**
```json
{
  "violations": {
    "agent_id": round_number_of_violation
  },
  "ban_until": {
    "agent_id": ban_expires_after_this_round
  },
  "excess_this_round": {
    "agent_id": excess_kg_returned
  },
  "tier_this_round": {
    "agent_id": "high" | "low"
  }
}
```

**Behavior:**

1. **is_eligible(agent_id):**
   - Check if banned[agent_id] > current_round → False
   - Return True otherwise

2. **describe(agent_id):**
   - Show current reserve level and tier classification
   - Show applicable limit based on tier:
     * High tier (≥20kg): min(25% of stock, 30kg)
     * Low tier (<20kg): min(12% of stock, 15kg)
   - Show current lake stock
   - If banned: "You are banned from fishing until round X."
   - If has violation history: warning note

3. **evaluate(agent_id, raw_kg):**
   - Step 1: Determine tier based on reserves
     - reserves = payoff[agent_id]
     - tier = "high" if reserves >= 20.0 else "low"
   - Step 2: Calculate allowed amount based on tier
     - If high: limit = min(stock * 0.25, 30.0)
     - If low: limit = min(stock * 0.12, 15.0)
   - Step 3: Check for violation
     - If raw_kg > limit:
       - excess = raw_kg - limit
       - kept = limit
       - Record violation at current round
       - Record ban for next round
       - Record excess to be returned
       - Return violation decision
     - Else:
       - Return allow decision

4. **on_round_end():**
   - Sum all excess_this_round amounts
   - Add to stock via override_stock_after_regrowth()
   - Clear round-specific tracking

### Config Activation

Update state/config.json["norms"] to REPLACE existing norm:
```json
[{
  "type": "tiered_catch_limit_with_forfeiture",
  "id": "round_3_limit",
  "high_reserve_threshold": 20.0,
  "high_reserve_percent": 0.25,
  "high_reserve_kg_cap": 30.0,
  "low_reserve_percent": 0.12,
  "low_reserve_kg_cap": 15.0,
  "ban_rounds": 1
}]
```

### Institution Update

Update state/institution.json["norm_types"]:
```json
{
  "tiered_catch_limit_with_forfeiture": {
    "description": "Enforces tiered catch limits based on reserve levels: high reserves (≥20kg) get 25%/30kg limit, low reserves (<20kg) get 12%/15kg limit, with immediate forfeiture of excess and one-trip bans",
    "owner": "norms/tiered_catch_limit_with_forfeiture.py"
  }
}
```

### Fluent for Norm Active

Update state/fluents.json:
- End fluent: norm_active, args={"type": "catch_limit_with_tax_and_ban"}, round=3
- New fluent: norm_active, args={"type": "tiered_catch_limit_with_forfeiture"}, holder=community, round=3

### Fluent Schema Update

Add to state/fluents_schema.md:
- `tier_classification` - Indicates a fisher's reserve tier (high/low) for catch limit purposes
- `excess_returned` - Amount of catch returned to lake due to limit violation

---

## Verification Matrix

| Requirement | Shape | Owner | Verification |
|-------------|-------|-------|--------------|
| Tiered catch limits (25%/30kg vs 12%/15kg) | catch_constraint | norms/tiered_catch_limit_with_forfeiture.py | tests/norm_checks/test_round_3_tiered.py |
| Immediate excess forfeiture | stock_adjustment | norms/tiered_catch_limit_with_forfeiture.py | tests/norm_checks/test_round_3_tiered.py |
| Ban after violation | eligibility_check | norms/tiered_catch_limit_with_forfeiture.py | tests/norm_checks/test_round_3_tiered.py |
| Transparency/public ledger | information_display | norms/tiered_catch_limit_with_forfeiture.py | tests/norm_checks/test_round_3_tiered.py |

---

```json
{
  "requirements": [
    {
      "id": 1,
      "description": "Tiered catch limits: high reserves (≥20kg) get min(25% of stock, 30kg), low reserves (<20kg) get min(12% of stock, 15kg)",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/tiered_catch_limit_with_forfeiture.py",
      "parametric": false
    },
    {
      "id": 2,
      "description": "Immediate forfeiture of excess catch (returned to lake stock)",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/tiered_catch_limit_with_forfeiture.py",
      "parametric": false
    },
    {
      "id": 3,
      "description": "Reserve-based state field tracking (using payoff)",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/tiered_catch_limit_with_forfeiture.py",
      "parametric": false
    },
    {
      "id": 4,
      "description": "One-trip ban for violations",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/tiered_catch_limit_with_forfeiture.py",
      "parametric": false
    },
    {
      "id": 5,
      "description": "Ban lift after ban period expires",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/tiered_catch_limit_with_forfeiture.py",
      "parametric": false
    },
    {
      "id": 6,
      "description": "Reserve recording before departure",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Reserves automatically tracked; no separate recording step exists"
    },
    {
      "id": 7,
      "description": "Catch logging after trip",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Catch automatically recorded by physics; no manual logging step exists"
    },
    {
      "id": 8,
      "description": "Rotating lake monitor selection",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Monitor duties are deterministic calculations, no judgment required"
    },
    {
      "id": 9,
      "description": "Lake stock update by monitor",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Stock updates are automatic, no manual update needed"
    },
    {
      "id": 10,
      "description": "Ledger broadcast to community notice board",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "State already visible to all agents; no separate broadcast needed"
    },
    {
      "id": 11,
      "description": "Non-compliance for failure to log catch",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Catch logging is automatic; failure case cannot occur"
    },
    {
      "id": 12,
      "description": "Transparency of ledger entries",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/tiered_catch_limit_with_forfeiture.py",
      "parametric": false
    }
  ],
  "actions_added": [],
  "norms_added": ["tiered_catch_limit_with_forfeiture"],
  "norms_replaced": ["catch_limit_with_tax_and_ban"]
}
```
