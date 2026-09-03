# Round 1 Norm Specification

## Policy
Each fisher may take a maximum of 4kg per trip, keeping 1kg for personal sustenance and leaving the rest in the lake or into a community reserve.

## Operationalization
At the start of each fishing day, all fishers will weigh their catch and record it in a shared ledger. If a fisher attempts to take more than 4kg, the surplus must be returned to the lake or donated to the reserve; the community steward will oversee compliance and may temporarily suspend a fisher's turn if limits are repeatedly breached. The reserve is used for emergencies and to support fish population recovery, with all catch contributions reported weekly in a communal meeting.

## Requirements

### R1: Per-Trip Catch Cap
**Text:** Each fisher's catch is limited to a maximum of 4kg per trip. Any amount caught above 4kg is considered excess and handled separately.

**Classification:** catch_constraint  
**Clarity:** CLEAR  
**Testable Formulation:** `harvested_kg <= 4` for the cap, with violation triggered when raw catch exceeds 4kg.

### R2: Personal Sustenance Minimum
**Text:** Each fisher keeps 1kg minimum for personal sustenance from their catch.

**Classification:** catch_constraint  
**Clarity:** CLEAR  
**Testable Formulation:** `kept_kg >= min(1, raw_kg)` - the fisher always keeps at least 1kg, or their full catch if under 1kg.

### R3: Remainder to Community Reserve
**Text:** The amount between the sustenance minimum and the catch cap goes to the community reserve.

**Classification:** catch_constraint  
**Clarity:** CLEAR  
**Testable Formulation:** `reserve_deposit = min(raw_kg, 4) - kept_kg` where `kept_kg = min(max(raw_kg, 0), 1)` effectively means 1kg sustenance kept, remainder to reserve.

### R4: Violation Sanction for Over-Cap Catch
**Text:** Catching more than 4kg triggers a violation sanction.

**Classification:** graduated_sanction trigger  
**Clarity:** CLEAR  
**Testable Formulation:** When `raw_kg > 4`, emit `sanction="over_cap"`.

### R5: Temporary Ban for Repeated Violations
**Text:** Fishers who repeatedly breach limits may be temporarily suspended from fishing.

**Classification:** graduated_sanction  
**Clarity:** AMBIGUOUS  
**Question Asked:** "How many violations constitute 'repeatedly breached' and for how many trips should a fisher be suspended?"  
**Answer Received:** (No clarification exchange available - implementing with best-effort interpretation)  
**Implemented Interpretation:** 2 violations trigger a 1-trip ban.

### R6: Community Steward Role
**Text:** A community steward oversees compliance with the catch limits.

**Classification:** role_fluent  
**Clarity:** CLEAR  
**Testable Formulation:** Assign `steward` role to one agent who is informed of violations.

### R7: Weekly Reporting (Not Operationalizable)
**Text:** All catch contributions are reported weekly in a communal meeting.

**Classification:** reporting_obligation  
**Clarity:** TECHNICALLY_UNREALISABLE  
**Note:** The simulation has no concept of elapsed time within a round or separate reporting actions. The weekly reporting requirement is not implemented; only the numeric enforcement mechanisms are operationalized.

## Classification Table

| Rule Fragment | Shape | Parameters | Owner | Verification |
|---------------|-------|------------|-------|--------------|
| 4kg catch cap | catch_constraint | limit_kg: 4 | norms/catch_limit.py (catch_limit) | tests/norm_checks/test_round_1.py |
| 1kg sustenance keep | catch_constraint | sustenance_kg: 1 | norms/sustenance_reserve.py (sustenance_reserve) | tests/norm_checks/test_round_1.py |
| Remainder to reserve | catch_constraint | auto_deposit: true | norms/sustenance_reserve.py (sustenance_reserve) | tests/norm_checks/test_round_1.py |
| Violation sanction trigger | graduated_sanction trigger | sanction: "over_cap" | norms/catch_limit.py (catch_limit) | tests/norm_checks/test_round_1.py |
| Temporary ban for repeat violations | graduated_sanction | trigger_sanction: "over_cap", trips: 1, threshold: 2 | norms/violation_ban.py (violation_ban) | tests/norm_checks/test_round_1.py |
| Steward role assignment | role_fluent | role: "steward" | state/fluents.json + prompts/role_directives/steward.md | tests/norm_checks/test_round_1.py |

## Implementation Notes

### Norm Ordering
The enforcement order in `state["config"]["norms"]` is critical:
1. `sustenance_reserve` (enforces 1kg keep, deposits remainder to reserve)
2. `catch_limit` (enforces 4kg cap, emits violation if exceeded)
3. `violation_ban` (applies ban after 2 violations)

Wait - this order is wrong. The catch_limit must come BEFORE sustenance_reserve to cap the amount first, then the sustenance_reserve processes the capped amount. Actually, rethinking:

The sustenance_reserve needs to:
1. Cap at 4kg
2. Keep 1kg for fisher
3. Deposit (capped_amount - 1kg) to reserve
4. Emit violation if raw > 4

This is a single norm that combines cap + sustenance + reserve deposit.

### Alternative: Single Norm Approach
Create `sustenance_cap` norm that:
- Caps at max_kg (4kg)
- Guarantees min_keep (1kg)
- Deposits (capped - min_keep) to reserve
- Emits violation if raw > max_kg

This is cleaner than chaining multiple norms.

## Institutional Changes

No new phases required. All constraints are deterministic calculations that happen within the harvest phase's norm chain.

### State Changes
- `state/config.json`: Add norms configuration
- `state/fluents.json`: Add steward role assignment
- `prompts/role_directives/steward.md`: Create steward role directive

## Machine-Readable Specification

```json
{
  "round": 1,
  "policy": "Each fisher may take a maximum of 4kg per trip, keeping 1kg for personal sustenance and leaving the rest in the lake or into a community reserve.",
  "requirements": [
    {
      "id": "R1",
      "text": "Each fisher's catch is limited to a maximum of 4kg per trip",
      "shape": "catch_constraint",
      "clarity": "CLEAR",
      "parameters": {"max_kg": 4}
    },
    {
      "id": "R2",
      "text": "Each fisher keeps 1kg minimum for personal sustenance",
      "shape": "catch_constraint",
      "clarity": "CLEAR",
      "parameters": {"sustenance_kg": 1}
    },
    {
      "id": "R3",
      "text": "Amount between sustenance and cap goes to community reserve",
      "shape": "catch_constraint",
      "clarity": "CLEAR",
      "parameters": {"deposit_to_reserve": true}
    },
    {
      "id": "R4",
      "text": "Catching more than 4kg triggers violation sanction",
      "shape": "graduated_sanction",
      "clarity": "CLEAR",
      "parameters": {"sanction": "over_cap"}
    },
    {
      "id": "R5",
      "text": "Repeated violations result in temporary suspension",
      "shape": "graduated_sanction",
      "clarity": "AMBIGUOUS",
      "parameters": {"threshold": 2, "ban_trips": 1},
      "note": "Best-effort interpretation: 2 violations trigger 1-trip ban"
    },
    {
      "id": "R6",
      "text": "Community steward oversees compliance",
      "shape": "role_fluent",
      "clarity": "CLEAR",
      "parameters": {"role": "steward"}
    },
    {
      "id": "R7",
      "text": "Weekly reporting of contributions",
      "shape": "reporting_obligation",
      "clarity": "TECHNICALLY_UNREALISABLE",
      "note": "Timing/logging not operationalizable in simulation"
    }
  ],
  "institutional_changes": {
    "add_phases": [],
    "add_state": [],
    "add_norms": ["sustenance_reserve"],
    "add_roles": ["steward"]
  }
}
```
