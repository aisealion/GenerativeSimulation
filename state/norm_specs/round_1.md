# Round 1 Norm Specification

## Policy
No fisher may take more than 8 kg per trip and the lake must retain at least 30% of its current biomass after each round.

## Operationalization
Each evening the crew records each person's haul on a shared ledger; the community sums the total catch and subtracts it from the lake's known stock. If anyone exceeds the 8 kg limit, that fisher must return the surplus to the lake and is barred from fishing for the next round. If the remaining biomass falls below 30% of the current stock, the community imposes a temporary moratorium and revises the quotas before fishing resumes.

## Rule Fragment Classification

| Fragment | Shape | Parameters | Owner | Verification |
|----------|-------|------------|-------|--------------|
| Per-fisher 8kg cap | catch_constraint | limit_kg: 8 | norms/catch_limit.py (catch_limit) | tests/norm_checks/test_round_1.py |
| Ban for exceeding cap | graduated_sanction | trigger_sanction: "over_cap", trips: 1 | norms/violation_ban.py (violation_ban) | tests/norm_checks/test_round_1.py |
| Community 70% cap | catch_constraint | cap_pct_of_stock: 0.7 | norms/community_cap.py (community_cap) | tests/norm_checks/test_round_1.py |

## Requirements

### R1: Per-Fisher Catch Limit
- **Text**: Each fisher may keep at most 8 kg from any single trip.
- **Clarity**: CLEAR
- **Testable Condition**: For any harvest phase, `harvested_kg(agent) <= 8` for all agents.

### R2: Surplus Return on Violation
- **Text**: If a fisher's raw catch exceeds 8 kg, the surplus (amount over 8 kg) is not kept.
- **Clarity**: CLEAR
- **Testable Condition**: If `raw_kg > 8`, then `kept_kg = 8` and the decision carries sanction "over_cap".

### R3: One-Round Ban for Cap Violation
- **Text**: A fisher who exceeds the 8 kg limit is barred from fishing in the next round.
- **Clarity**: CLEAR
- **Testable Condition**: If an agent's decision in round N has sanction "over_cap", then in round N+1, `is_eligible(agent) = False`.

### R4: Community Biomass Retention
- **Text**: The community's total catch in a round cannot exceed 70% of the lake's stock at the start of that round (ensuring at least 30% remains).
- **Clarity**: CLEAR
- **Testable Condition**: `sum(harvested_kg) <= 0.7 * stock_kg_before` for the round.

### R5: Community Cap Enforcement Order
- **Text**: The community cap is enforced first-come-first-served based on agent iteration order.
- **Clarity**: CLEAR
- **Testable Condition**: Once the running tally reaches 70% of stock, subsequent agents in that round receive `kept_kg = 0` with sanction "over_community_cap".

### R6: Moratorium Trigger (Partial Implementation)
- **Text**: If remaining biomass falls below 30% of current stock, impose a temporary moratorium.
- **Clarity**: INCOMPLETE
- **Note**: The operationalization describes a reactive moratorium after the fact, but the simulation architecture enforces caps proactively during harvest. The `community_cap` plugin prevents the biomass from falling below 30% by capping total catch at 70%. The "temporary moratorium and revises quotas" portion describes a decision process (quota revision) that would require a new phase, but the core protective constraint (preventing stock from dropping below 30%) is operationalized via the community cap. This is a best-effort approximation given current architecture.

## Implementation Notes

### Config Order
The norms in `state["config"]["norms"]` must be ordered as:
1. `catch_limit` (individual cap) - evaluates individual violations first
2. `community_cap` (community cap) - tracks running total after individual caps
3. `violation_ban` (ban enforcement) - activates on "over_cap" sanction

This ordering ensures:
- Individual caps are applied and violations flagged before community tally
- Community cap sees the post-cap amounts when computing its running total
- Ban is triggered by violations from the catch_limit norm

### No New Phase Required
All rule fragments are deterministic constraints on harvest quantities and consequences. No agent decision beyond the existing harvest phase is required. The "revises quotas" language in the operationalization describes a potential community response, not an additional agent decision point.

### No Structural Changes Required
All fragments can be implemented using existing norm plugins:
- `catch_limit` for the 8kg per-fisher cap
- `violation_ban` for the one-round fishing ban
- `community_cap` for the 70% community catch limit

## Machine-Readable Summary

```json
{
  "round": 1,
  "policy": "No fisher may take more than 8 kg per trip and the lake must retain at least 30% of its current biomass after each round",
  "fragments": [
    {
      "id": "F1",
      "shape": "catch_constraint",
      "parametric": true,
      "type": "catch_limit",
      "config": {"type": "catch_limit", "limit_kg": 8}
    },
    {
      "id": "F2",
      "shape": "graduated_sanction",
      "parametric": true,
      "type": "violation_ban",
      "config": {"type": "violation_ban", "trigger_sanction": "over_cap", "trips": 1}
    },
    {
      "id": "F3",
      "shape": "catch_constraint",
      "parametric": true,
      "type": "community_cap",
      "config": {"type": "community_cap", "cap_pct_of_stock": 0.7}
    }
  ],
  "requirements": [
    {"id": "R1", "clarity": "CLEAR", "fragment": "F1"},
    {"id": "R2", "clarity": "CLEAR", "fragment": "F1"},
    {"id": "R3", "clarity": "CLEAR", "fragment": "F2"},
    {"id": "R4", "clarity": "CLEAR", "fragment": "F3"},
    {"id": "R5", "clarity": "CLEAR", "fragment": "F3"},
    {"id": "R6", "clarity": "INCOMPLETE", "fragment": "F3", "note": "Moratorium mechanism approximated by proactive community cap"}
  ],
  "institutional_changes": {
    "add_phases": [],
    "add_state": {},
    "config_norms_order": ["catch_limit", "community_cap", "violation_ban"]
  }
}
```
