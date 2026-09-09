# Round 1 Norm Specification

## Source Norm

**Policy:** Record expected catch before departure; log actual catch upon return; update lake stock daily; any catch over 15% of the current stock or 20 kg is forfeited, returned to the communal pool, and the fisher receives a one-day ban; failure to record expected or actual catch results in the same forfeiture and ban; the communal ledger is reviewed daily by the community committee to enforce compliance.

**Operationalization:**
1. Before leaving the dock, each fisher writes their expected catch in the communal ledger book kept in the dock hall, under their name and date.
2. Upon return, the fisher records the actual catch in the same ledger; if the actual catch is missing, the fisher is treated as if they may have exceeded limits.
3. The chair, elected by consensus and rotating monthly, opens the ledger each night to update the lake's stock: the new stock equals previous stock plus any forfeited fish, minus the allowed catch of each fisher.
4. The 15% limit is applied using the stock level at the moment of departure; any actual haul exceeding the lesser of 15% of that stock or 20 kg has the excess weight marked as "forfeited" on the ledger, added back to the lake's stock, and the fisher receives a one-day ban recorded as "ban_until" (date +1).
5. If a fisher fails to write an expected catch before departure or fails to record an actual catch upon return, the chair issues a one-day ban, treats any unlogged catch as forfeited, and records the incident in the ledger.
6. The community committee—consisting of the three most seasoned fishers, the elder, and a neutral mediator—reviews the ledger daily at the dock hall. They verify ban dates against fisher IDs at launch slips; a dock officer denies permission to launch to any fisher whose ban_until date is still in the future.
7. All licensed fishers can view ledger entries but only the chair may alter stock numbers or impose bans.
8. The ledger is the single source of truth; it is physically protected at night and checked for tampering each morning.
9. This system ensures transparency, accountability, and equitable use of the lake's bounty.

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

**Active Norms:** None (state/config.json["norms"] is empty)

---

## Requirement Analysis

### Requirement 1: Catch Limit Enforcement (15% or 20kg)

**Clarity:** CLEAR

- **Purpose:** Prevent any single fisher from taking too large a share of the lake's stock
- **Actor:** System/chair (deterministic enforcement)
- **Action/Decision:** Calculate limit as min(15% of current stock, 20kg), enforce cap
- **Existing action or new action:** Norm plugin (norms/*.py)
- **Inputs:** Current stock level, actual catch amount
- **Outputs:** Forfeited amount, kept amount, ban decision
- **State read:** runtime["stock_kg"]
- **State changed:** runtime["norms"][key]["forfeited_kg"], runtime["norms"][key]["ban_until"]
- **Timing / Frequency:** Every harvest action, per agent
- **Participation:** All fishers
- **Gate:** N/A (always active)
- **Institutional consequence:** Excess catch forfeited to communal pool, one-day ban issued
- **Agent-visible information:** Note explaining violation, ban_until date
- **Verification:** Test catch at exactly 15%, at 20kg, above both limits, below both limits

### Requirement 2: Ban Eligibility Check

**Clarity:** CLEAR

- **Purpose:** Prevent banned fishers from fishing during their ban period
- **Actor:** System (deterministic check)
- **Action/Decision:** Check if current round < ban_until round for each fisher
- **Existing action or new action:** Norm plugin (norms/*.py) via is_eligible()
- **Inputs:** Agent ID, ban_until dates
- **Outputs:** Eligibility boolean
- **State read:** runtime["norms"][key]["ban_until"]
- **State changed:** None (read-only check)
- **Timing / Frequency:** Every harvest action, before each agent's turn
- **Participation:** All fishers with active bans
- **Gate:** N/A
- **Institutional consequence:** Banned agents skip fishing (no LLM call)
- **Agent-visible information:** Constraints line noting ban status
- **Verification:** Test fisher with active ban, fisher with expired ban

### Requirement 3: Forfeited Fish Added Back to Stock

**Clarity:** CLEAR

- **Purpose:** Ensure forfeited fish remain in the lake (communal pool)
- **Actor:** System/chair (deterministic process)
- **Action/Decision:** Sum all forfeited amounts, add to post-regrowth stock
- **Existing action or new action:** Norm plugin (norms/*.py) via on_round_end()
- **Inputs:** All forfeited amounts from this round
- **Outputs:** Updated stock level
- **State read:** All forfeited_kg from norm_state
- **State changed:** context.override_stock_after_regrowth()
- **Timing / Frequency:** End of each harvest round
- **Participation:** N/A (system process)
- **Gate:** N/A
- **Institutional consequence:** Stock increased by forfeited amount
- **Agent-visible information:** None (stock update is background process)
- **Verification:** Test forfeited amounts are correctly added to stock

### Requirement 4: Recording Expected Catch

**Clarity:** TECHNICALLY_UNREALISABLE

**Rationale:** The norm asks fishers to "write their expected catch" before departure, but this is separate from their actual harvest effort decision. Implementing this would require a new action before harvest where fishers declare expected catch, but the norm doesn't specify how this expectation is enforced or what constitutes a "failure to record." The simulation's agent architecture makes the harvest decision (effort) atomic with the catch outcome. Without a clear enforcement mechanism or consequence specification for the expected catch recording specifically (separate from actual catch recording), this requirement cannot be deterministically implemented. The closest realizable element is the actual catch limit enforcement (Requirement 1).

### Requirement 5: Recording Actual Catch

**Clarity:** TECHNICALLY_UNREALISABLE  

**Rationale:** Similar to Requirement 4, the norm asks fishers to "record the actual catch" upon return. In the simulation, the actual catch is automatically computed by physics and recorded in the round results. The norm's consequence for "fails to record actual catch" is unclear in a system where the catch is automatically tracked. The norm seems to imagine a separate reporting step that doesn't exist in the current architecture, and adding one would require a new action and significant architectural changes beyond the scope of a norm plugin.

### Requirement 6: Chair Role

**Clarity:** AMBIGUOUS

**Rationale:** The norm specifies a "chair" who updates the ledger, but the operationalization describes deterministic processes (calculating limits, marking forfeits, issuing bans) that don't require judgment. The chair appears to be a ceremonial role for actions that are algorithmically determined. However, the norm says the chair is "elected by consensus and rotating monthly." Since the simulation enforces norms deterministically through the NormEngine, an explicit chair role isn't needed for the limit enforcement logic to function.

**Question to proposer:** Does the chair have any discretionary decisions, or are all their actions (calculating forfeitures, issuing bans) purely mechanical based on the catch data?

**Clarification needed:** If purely mechanical, can we treat the "chair" as a conceptual role fulfilled by the system/norm engine, or must there be an explicit elected agent who performs these checks?

### Requirement 7: Community Committee Verification

**Clarity:** INCOMPLETE

**Rationale:** The committee is described as reviewing the ledger and verifying ban dates, but the enforcement (denying launch) is already handled by the dock officer based on ban_until dates. The committee's role doesn't add any enforceable mechanism beyond what the ban system already provides. It's unclear what the committee actually decides vs. what is automatic.

### Requirement 8: Ledger as Single Source of Truth

**Clarity:** CLEAR

**Rationale:** The simulation's runtime["norms"][key] state serves as the ledger. This is already satisfied by using norm_state for persistent ban and forfeiture tracking.

---

## Design Decisions

### Parametric vs. Structural

All realizable requirements (1, 2, 3) route to a single new norm plugin: **catch_limit_with_forfeiture**

This norm type will:
- Track ban_until dates per fisher (cross-round persistent state)
- Check eligibility based on ban status (is_eligible)
- Calculate limit = min(stock * 0.15, 20) (evaluate)
- Enforce cap with forfeiture for excess (evaluate)
- Return forfeited fish to stock (on_round_end)

Requirements 4, 5, 6, 7 are not implemented due to being technically unrealizable or incomplete given current simulation architecture.

### Why no new actions?

The requirements that would need new actions (recording expected/actual catch) either:
1. Don't have clear enforcement mechanisms in the norm (what exactly constitutes a "failure to record")
2. Are ceremonial roles that don't add judgment-based decisions

The core enforceable rule (15% or 20kg limit with forfeiture and bans) is purely deterministic and properly belongs in a norm plugin.

---

## Implementation Plan

### New Norm Type: catch_limit_with_forfeiture

**File:** norms/catch_limit_with_forfeiture.py
**Type name:** catch_limit_with_forfeiture
**Parameters:**
- percent_limit: 0.15 (15%)
- kg_limit: 20.0 (20kg)
- ban_days: 1

**State Schema:**
```json
{
  "bans": {
    "agent_id": ban_until_round_number
  },
  "forfeited_this_round": {
    "agent_id": forfeited_kg
  }
}
```

**Behavior:**
1. is_eligible(): Returns False if agent has ban_until > current round
2. describe(): Returns ban notice if banned, limit info if not
3. evaluate(): 
   - Calculate limit = min(stock * 0.15, 20.0)
   - If raw_kg > limit: forfeited = raw_kg - limit, kept = limit
   - Record ban_until = current_round + 1
   - Return violation decision
4. on_round_end(): Sum all forfeited amounts, add to stock via override

### Config Activation

Update state/config.json["norms"]:
```json
[{
  "type": "catch_limit_with_forfeiture",
  "id": "round_1_limit",
  "percent_limit": 0.15,
  "kg_limit": 20.0,
  "ban_days": 1
}]
```

### Institution Update

Update state/institution.json["norm_types"]:
```json
{
  "catch_limit_with_forfeiture": {
    "description": "Enforces a catch limit (percent of stock or kg, whichever is less) with forfeiture of excess and one-day bans for violations",
    "owner": "norms/catch_limit_with_forfeiture.py"
  }
}
```

### Fluent for Norm Active

Add norm_active fluent on activation:
- fluent: norm_active
- args: {"type": "catch_limit_with_forfeiture"}
- holder: community

---

## Verification Matrix

| Requirement | Shape | Owner | Verification |
|-------------|-------|-------|--------------|
| Catch limit (15% or 20kg) | catch_constraint | norms/catch_limit_with_forfeiture.py | tests/norm_checks/test_round_1_limit.py |
| Ban eligibility | eligibility_check | norms/catch_limit_with_forfeiture.py | tests/norm_checks/test_round_1_limit.py |
| Forfeited to stock | stock_adjustment | norms/catch_limit_with_forfeiture.py | tests/norm_checks/test_round_1_limit.py |

---

```json
{
  "requirements": [
    {
      "id": 1,
      "description": "Catch limit enforcement: min(15% of stock, 20kg)",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_forfeiture.py",
      "parametric": false
    },
    {
      "id": 2,
      "description": "Ban eligibility check",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_forfeiture.py",
      "parametric": false
    },
    {
      "id": 3,
      "description": "Forfeited fish returned to stock",
      "clarity": "CLEAR",
      "implemented": true,
      "shape": "norm_plugin",
      "owner": "norms/catch_limit_with_forfeiture.py",
      "parametric": false
    },
    {
      "id": 4,
      "description": "Recording expected catch",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Requires new pre-harvest action with unclear enforcement"
    },
    {
      "id": 5,
      "description": "Recording actual catch",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "implemented": false,
      "reason": "Catch automatically recorded; unclear what failure means"
    },
    {
      "id": 6,
      "description": "Chair role for enforcement",
      "clarity": "AMBIGUOUS",
      "implemented": false,
      "reason": "Actions are deterministic, no judgment required; role ceremonial"
    },
    {
      "id": 7,
      "description": "Community committee verification",
      "clarity": "INCOMPLETE",
      "implemented": false,
      "reason": "Unclear what committee decides vs automatic enforcement"
    }
  ],
  "actions_added": [],
  "norms_added": ["catch_limit_with_forfeiture"]
}
```
