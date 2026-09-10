# Round 1 Norm Specification

## Policy Statement (from norm.txt)

Each fisher may take no more than 10% of the lake's current stock per trip, capped at 10 kg, and the community's total weekly catch may not exceed 20% of the lake stock at the week's start; excess must be donated to the communal store and accompanied by 2 hours of community service, and if the lake stock falls below 150 kg, all fishing stops for four weeks until the stock recovers to at least 150 kg, after which the council authorizes a resume.

## Operationalization Summary (from norm.txt)

1. Before each trip, fisher consults weekly lake stock estimate; per-trip limit is 10% of that stock, capped at 10 kg.
2. After each trip, fisher records actual catch weight in communal ledger (digital backup) and signs it; ledger keeper verifies.
3. Council (rotating active fishers, village elder, neutral observer) reviews ledger every Monday.
4. If fisher exceeds per-trip limit, excess is donated to communal store and fisher performs 2 hours community service.
5. Council sums weekly catches and compares to 20% of lake stock at week's start; if exceeded, excess donated to communal store, all contributing fishers perform 2 hours community service, and fishing suspended for one week.
6. Lake stock estimated weekly by fishery officer using 50-meter seine net in predetermined area; officer records total weight and area sampled, divides to estimate stock, logs in ledger.
7. If estimated stock falls below 150 kg, council orders four-week fishing stop; after four weeks council re-measures, and if at least 150 kg, announces fishing may resume via ledger and radio.
8. Roles (fishery officer, ledger keeper) elected by rotating nomination and show-of-hands each month; fishery officer performs weekly survey, ledger keeper verifies entries.
9. All fishers may view ledger; only keeper may modify or approve entries.
10. Council ensures compliance by checking ledger entries and issuing penalties.

---

## Current Institution Status (Section 2)

**Actions:**
- harvest: Each alive fisher decides effort (0.0-1.0), physics converts to catch. No constraints currently active.
- propose: Each fisher proposes candidate community rule.
- critique: Proposals refined through bounded critique-and-revise dialogue.
- vote: Each fisher votes on refined proposals.
- discuss: Currently unimplemented stub, gated off.

**Roles:**
- fisher: Base role every agent holds from round 0 (eligibility to act as fisher).
- dead: Permanent status for agents with negative food balance.

**State:**
- Per-fisher: effort, harvested_kg, payoff
- Community: stock_kg

**Norms:** None currently active (state/config.json "norms": [])

---

## Requirement Extraction (Section 4)

### Requirement 1: Per-Trip Catch Limit
**Clarity:** CLEAR

- **Actor:** Individual fisher (per-trip constraint)
- **Verb/Action:** May take no more than min(10% of current stock, 10 kg)
- **Deterministic check:** Yes - simple arithmetic comparison
- **Routing:** norms/*.py plugin (deterministic constraint)

**Details:**
- Before each trip, limit = min(stock_kg * 0.10, 10.0)
- If raw catch > limit, excess donated, fisher keeps limit
- Violation triggers: 2 hours community service (recorded as sanction)

---

### Requirement 2: Weekly Community Total Limit
**Clarity:** CLEAR

- **Actor:** Community (aggregate constraint)
- **Verb/Action:** Total weekly catch may not exceed 20% of week's starting stock
- **Deterministic check:** Yes - sum comparison at round end
- **Routing:** norms/*.py plugin with on_round_end hook

**Details:**
- Track running total of kept catches during round
- At round end, compare total to 0.20 * stock_at_round_start
- If exceeded: excess donated to communal store
- All contributing fishers perform 2 hours community service
- Fishing suspended for one week (implementation: ban all fishers for 1 round)

---

### Requirement 3: Stock Collapse Protection (150 kg threshold)
**Clarity:** CLEAR

- **Actor:** Community (system-level protection)
- **Verb/Action:** If stock < 150 kg, fishing stops for 4 weeks
- **Deterministic check:** Yes - threshold comparison
- **Routing:** norms/*.py plugin with is_eligible hook

**Details:**
- Check stock before each round
- If stock < 150 kg: all fishers ineligible (ban)
- Ban lasts exactly 4 rounds (weeks)
- After 4 rounds, check if stock >= 150 kg; if yes, lift ban
- If stock still < 150 kg, ban continues

---

### Requirement 4: Fishery Officer Role and Stock Estimation
**Clarity:** INCOMPLETE (for round 1 scope)

- **Actor:** Fishery officer (elected monthly)
- **Verb/Action:** Estimates stock weekly using seine net sampling
- **Deterministic check:** No - this requires judgment/estimation
- **Routing:** Action-shaped, but simulation already knows true stock

**Resolution for Round 1:**
The simulation already has perfect stock information in runtime["stock_kg"]. The norm's estimation procedure (sampling, calculation) is meant to introduce potential error/human judgment, but implementing a full estimation action with elected officer role is complex institutional infrastructure beyond round 1's core constraints. For this round, the stock value used by norms will be the simulation's ground truth (physics stock). A future round could introduce the fishery officer role and estimation action with potential error.

**Decision:** Defer full implementation. The per-trip limit norm (Req 1) will use the physics stock value directly as a simplification.

---

### Requirement 5: Ledger Keeper Role and Ledger Recording
**Clarity:** INCOMPLETE (for round 1 scope)

- **Actor:** Ledger keeper (elected monthly)
- **Verb/Action:** Records catches in communal ledger, verifies entries
- **Deterministic check:** No - requires judgment on verification
- **Routing:** Action-shaped

**Resolution for Round 1:**
The ledger is meant to be a persistent record visible to all fishers. Implementing this requires:
1. A ledger keeper role with election mechanism
2. A recording action where the keeper records each fisher's catch
3. Verification judgment by the keeper

This is significant infrastructure. For round 1, the simulation's existing runtime record of catches serves as the "ledger" - it's already persistent and queryable. The keeper role and explicit recording action are deferred to a future round when the election infrastructure can be properly implemented.

**Decision:** Defer full implementation. Use simulation runtime as implicit ledger.

---

### Requirement 6: Council Role and Weekly Review
**Clarity:** INCOMPLETE (for round 1 scope)

- **Actor:** Council (rotating active fishers, village elder, neutral observer)
- **Verb/Action:** Reviews ledger every Monday, sums catches, issues penalties
- **Deterministic check:** Mixed - summing is arithmetic, but "review" and penalty issuance implies judgment
- **Routing:** Action-shaped

**Resolution for Round 1:**
The council's review functions are:
1. Verify ledger entries (Req 5 - deferred)
2. Sum weekly catches and compare to limit (Req 2 - automated in norm plugin)
3. Issue penalties for violations (Req 1 & 2 - automated in norm plugin)

The automated norm plugins will handle the arithmetic constraints (per-trip cap, weekly total cap). The council's judgment role in reviewing and ruling on violations is deferred until the council role and meeting action can be properly implemented with elections.

**Decision:** Defer full implementation. Arithmetic enforcement via norm plugins.

---

### Requirement 7: Elections for Roles
**Clarity:** CLEAR but TECHNICALLY_UNREALISABLE at current scope

- **Actor:** Community
- **Verb/Action:** Elect fishery officer and ledger keeper monthly via rotating nomination and show-of-hands
- **Deterministic check:** No - genuine collective decision
- **Routing:** Requires new election action, role assignment mechanism

**Resolution for Round 1:**
Election infrastructure (nomination, voting on roles, monthly rotation) is complex and would require significant new actions. This is foundational institutional machinery that would support Req 4, 5, and 6. Without this, those roles cannot function as specified.

**Decision:** Defer to future round. For round 1, no elected roles; enforcement is automatic via norm plugins.

---

### Requirement 8: Community Service for Violations
**Clarity:** CLEAR

- **Actor:** Violating fisher
- **Verb/Action:** Perform 2 hours community service when excess caught
- **Deterministic check:** Yes - triggered automatically on violation
- **Routing:** norms/*.py plugin (sanction recording)

**Details:**
- Recorded as a sanction/violation in the norm system
- Community service is a penalty/status, not a physical action in this simulation
- Tracked via norm decision sanction field and potentially fluents for visibility

---

### Requirement 9: Communal Store for Excess
**Clarity:** CLEAR

- **Actor:** System (community resource)
- **Verb/Action:** Excess catch donated to communal store
- **Deterministic check:** Yes - automatic transfer
- **Routing:** norms/*.py plugin (catch reduction)

**Details:**
- When a fisher exceeds their limit, the excess amount is "donated" (they don't keep it)
- The communal store is a community resource - excess fish are still harvested from the lake but don't benefit the individual fisher
- For round 1, this is implemented as: fisher keeps = min(limit, raw_catch); excess = raw_catch - kept (not added to fisher's payoff)

---

### Requirement 10: One-Week Suspension for Weekly Limit Violation
**Clarity:** CLEAR

- **Actor:** All contributing fishers (community-level sanction)
- **Verb/Action:** Fishing suspended for one week when weekly total exceeded
- **Deterministic check:** Yes - automatic at round end
- **Routing:** norms/*.py plugin (ban for 1 round)

**Details:**
- Applied at end of round if community total > 20% of starting stock
- All fishers who contributed to the excess are banned for 1 round
- Banned fishers are ineligible to fish next round

---

## Institutional Design Summary (Section 5)

### Requirements Selected for Round 1 Implementation

| Req # | Requirement | Shape | Owner | Verification |
|-------|-------------|-------|-------|--------------|
| 1 | Per-trip limit (10% or 10kg cap) | catch_constraint | norms/per_trip_cap.py | test_round_1_per_trip_cap.py |
| 2 | Weekly community total (20% cap) | community_constraint | norms/weekly_total_cap.py | test_round_1_weekly_total.py |
| 3 | Stock collapse protection (150kg threshold) | eligibility_gate | norms/stock_protection.py | test_round_1_stock_protection.py |
| 8 | Community service sanction | sanction_record | (embedded in Req 1 & 2 norms) | (covered in Req 1 & 2 tests) |
| 9 | Communal store donation | catch_adjustment | (embedded in Req 1 & 2 norms) | (covered in Req 1 & 2 tests) |
| 10 | One-week suspension | eligibility_gate | (embedded in Req 2 norm) | (covered in Req 2 test) |

### Requirements Deferred

| Req # | Requirement | Reason |
|-------|-------------|--------|
| 4 | Fishery officer & estimation | Requires election infrastructure (Req 7); using physics stock as simplification |
| 5 | Ledger keeper & recording | Requires election infrastructure (Req 7); using runtime as implicit ledger |
| 6 | Council & weekly review | Requires election infrastructure (Req 7); arithmetic enforcement automated |
| 7 | Elections | Complex foundational machinery; deferred to enable 4, 5, 6 in future round |

---

## Detailed Design: Per-Trip Cap Norm

**Type name:** `per_trip_cap`

**Purpose:** Enforce individual per-trip catch limit of min(10% of stock, 10 kg)

**Parameters:**
- `stock_percentage`: 0.10 (10%)
- `absolute_cap_kg`: 10.0 (10 kg hard cap)

**Behavior:**
1. `evaluate()`: Calculate limit = min(stock_before * stock_percentage, absolute_cap_kg)
   - If raw_kg <= limit: `NormDecision.allow(raw_kg)`
   - If raw_kg > limit: `NormDecision.violation(limit, sanction="exceeded_per_trip_cap", note=f"You caught {raw_kg:.1f}kg but the per-trip limit is {limit:.1f}kg. The excess has been donated to the communal store. You must perform 2 hours of community service.")`

**State changed:** None (pure evaluation)

**Agent-visible:** Yes, via note on violation

---

## Detailed Design: Weekly Total Cap Norm

**Type name:** `weekly_total_cap`

**Purpose:** Enforce community weekly catch limit of 20% of starting stock

**Parameters:**
- `stock_percentage`: 0.20 (20%)
- `ban_rounds`: 1 (one week suspension)

**Behavior:**
1. `on_round_start()`: Initialize running total in round_scratch
2. `evaluate()`: Add proposed_kg to running total, allow catch through
3. `on_round_end()`: 
   - Calculate limit = stock_at_start * stock_percentage
   - If running total > limit:
     - Excess = total - limit
     - Identify all fishers who contributed (participated && harvested_kg > 0)
     - For each contributor: mark for ban next round, record sanction
     - Override note for all: "The community caught {total:.1f}kg, exceeding the weekly limit of {limit:.1f}kg. All contributing fishers must donate their excess, perform 2 hours of community service, and fishing is suspended for one week."

**State changed:**
- `runtime["norms"][key]["banned_agents"]` = list of agent_ids banned next round
- Persistent ban state tracked via norm_state

**Agent-visible:** Yes, via notes and ban status

---

## Detailed Design: Stock Protection Norm

**Type name:** `stock_protection_ban`

**Purpose:** Halt all fishing for 4 weeks if stock falls below 150 kg

**Parameters:**
- `threshold_kg`: 150.0
- `ban_weeks`: 4

**Behavior:**
1. `is_eligible()`: Check if agent is currently banned; return False if banned
2. `on_round_start()`: 
   - Check if ban is active (from previous rounds)
   - If ban active: decrement counter; if counter reaches 0, lift ban if stock >= threshold
   - If no ban active and stock < threshold: initiate ban for ban_weeks rounds
3. `describe()`: If banned, return "Fishing is suspended for [N] more weeks while the lake recovers."

**State changed:**
- `runtime["norms"][key]["ban_active"]` = bool
- `runtime["norms"][key]["ban_remaining_weeks"]` = int
- `runtime["norms"][key]["ban_reason"]` = string

**Agent-visible:** Yes, via describe() when ineligible

---

## Configuration

**state/config.json:**
```json
{
  "norms": [
    {"type": "stock_protection_ban", "threshold_kg": 150, "ban_weeks": 4},
    {"type": "per_trip_cap", "stock_percentage": 0.10, "absolute_cap_kg": 10},
    {"type": "weekly_total_cap", "stock_percentage": 0.20, "ban_rounds": 1}
  ]
}
```

**Order rationale:**
1. Stock protection first - if stock is critically low, no one fishes regardless of other rules
2. Per-trip cap second - limits individual catch before community aggregation
3. Weekly total last - operates on the sum of already-capped individual catches

---

## New Fluent Types

None required for round 1. Sanctions and bans are tracked via norm_state, not fluents.

---

## Implementation Verification

Each norm plugin will be tested with:
1. Compliance case: catch within limits, no violation
2. Violation case: catch exceeds limit, proper sanction applied
3. Edge case: exact limit boundary
4. For weekly total: multi-agent scenario testing aggregation logic

---

```json
{
  "round": 1,
  "requirements": [
    {"id": 1, "name": "Per-trip catch limit", "clarity": "CLEAR", "implemented": true, "shape": "norm_plugin", "type_name": "per_trip_cap"},
    {"id": 2, "name": "Weekly community total limit", "clarity": "CLEAR", "implemented": true, "shape": "norm_plugin", "type_name": "weekly_total_cap"},
    {"id": 3, "name": "Stock collapse protection", "clarity": "CLEAR", "implemented": true, "shape": "norm_plugin", "type_name": "stock_protection_ban"},
    {"id": 4, "name": "Fishery officer role", "clarity": "INCOMPLETE", "implemented": false, "reason": "Requires election infrastructure (Req 7); using physics stock as simplification"},
    {"id": 5, "name": "Ledger keeper role", "clarity": "INCOMPLETE", "implemented": false, "reason": "Requires election infrastructure (Req 7); using runtime as implicit ledger"},
    {"id": 6, "name": "Council review", "clarity": "INCOMPLETE", "implemented": false, "reason": "Requires election infrastructure (Req 7); arithmetic enforcement automated"},
    {"id": 7, "name": "Elections", "clarity": "TECHNICALLY_UNREALISABLE", "implemented": false, "reason": "Complex foundational machinery; deferred to future round"},
    {"id": 8, "name": "Community service sanction", "clarity": "CLEAR", "implemented": true, "shape": "embedded", "owner": "per_trip_cap, weekly_total_cap"},
    {"id": 9, "name": "Communal store", "clarity": "CLEAR", "implemented": true, "shape": "embedded", "owner": "per_trip_cap, weekly_total_cap"},
    {"id": 10, "name": "One-week suspension", "clarity": "CLEAR", "implemented": true, "shape": "embedded", "owner": "weekly_total_cap"}
  ],
  "norm_types_added": ["per_trip_cap", "weekly_total_cap", "stock_protection_ban"],
  "actions_added": [],
  "roles_added": [],
  "config_changes": ["state/config.json norms list"],
  "institution_changes": ["state/institution.json norm_types catalog"],
  "fluents_changes": ["norm_active tracking for new types"]
}
```
