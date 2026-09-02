# Round 3 Norm Specification

## Policy
No fisher may take more than 20kg per trip.

## Operationalization
Each fisher sets a 20kg limit on their catch before setting out. After each trip, the fisherman returns any weight exceeding 20kg back to the lake, and the community watches for infractions; repeated violations will result in a temporary fishing ban.

## Rule Fragment Classification

| Fragment | Shape | Parameters | Owner | Verification |
|----------|-------|------------|-------|--------------|
| Per-fisher 20kg cap | catch_constraint | limit_kg: 20 | norms/catch_limit.py (catch_limit) | tests/norm_checks/test_round_3.py |
| Return of excess | catch_constraint | (part of catch_limit) | norms/catch_limit.py (catch_limit) | tests/norm_checks/test_round_3.py |
| Ban for violations | graduated_sanction | trigger_sanction: "over_cap", trips: 2 | norms/violation_ban.py (violation_ban) | tests/norm_checks/test_round_3.py |

## Requirements

### R1: Per-Fisher Catch Limit
- **Text**: Each fisher may keep at most 20 kg from any single trip.
- **Clarity**: CLEAR
- **Testable Condition**: For any harvest phase, `harvested_kg(agent) <= 20` for all agents.

### R2: Surplus Return on Violation
- **Text**: If a fisher's raw catch exceeds 20 kg, the surplus (amount over 20 kg) is returned to the lake and not kept.
- **Clarity**: CLEAR
- **Testable Condition**: If `raw_kg > 20`, then `kept_kg = 20` and the decision carries sanction "over_cap".

### R3: Temporary Ban for Violations
- **Text**: A fisher who violates the 20kg limit is subject to a temporary fishing ban.
- **Clarity**: CLEAR
- **Testable Condition**: If an agent's decision in round N has sanction "over_cap", then in rounds N+1 through N+`trips`, `is_eligible(agent) = False`.
- **Note**: The operationalization mentions "repeated violations" triggering a ban. Since the simulation tracks individual violations per round and the violation_ban plugin activates on each sanction, each violation will trigger the ban mechanism. This implements the protective intent of deterring and penalizing non-compliant behavior.

### R4: Community Monitoring
- **Text**: The community watches for infractions.
- **Clarity**: INCOMPLETE
- **Note**: The operationalization describes community observation and detection of violations. In the simulation architecture, violation detection is automated through the norm evaluation pipeline rather than modeled as a separate community observation process. The sanction flagging mechanism serves the same protective function.

## Implementation Notes

### Config Order
The norms in `state["config"]["norms"]` must be ordered as:
1. `catch_limit` (individual 20kg cap) - evaluates individual violations first
2. `violation_ban` (ban enforcement) - activates on "over_cap" sanction

This ordering ensures:
- Individual caps are applied and violations flagged
- Ban is triggered by violations from the catch_limit norm

### No New Phase Required
All rule fragments are deterministic constraints on harvest quantities and consequences. No agent decision beyond the existing harvest phase is required. The "community watches for infractions" language describes a monitoring process that is approximated by the automated norm evaluation pipeline.

### No Structural Changes Required
All fragments can be implemented using existing norm plugins:
- `catch_limit` for the 20kg per-fisher cap
- `violation_ban` for the temporary fishing ban

The violation_ban plugin's `trips` parameter should be set to 2 to implement a meaningful "temporary" ban (skipping 2 rounds).

## Machine-Readable Summary

```json
{
  "round": 3,
  "policy": "No fisher may take more than 20kg per trip",
  "fragments": [
    {
      "id": "F1",
      "shape": "catch_constraint",
      "parametric": true,
      "type": "catch_limit",
      "config": {"type": "catch_limit", "limit_kg": 20}
    },
    {
      "id": "F2",
      "shape": "graduated_sanction",
      "parametric": true,
      "type": "violation_ban",
      "config": {"type": "violation_ban", "trigger_sanction": "over_cap", "trips": 2}
    }
  ],
  "requirements": [
    {"id": "R1", "clarity": "CLEAR", "fragment": "F1"},
    {"id": "R2", "clarity": "CLEAR", "fragment": "F1"},
    {"id": "R3", "clarity": "CLEAR", "fragment": "F2"},
    {"id": "R4", "clarity": "INCOMPLETE", "fragment": null, "note": "Community observation process approximated by automated norm evaluation"}
  ],
  "institutional_changes": {
    "add_phases": [],
    "add_state": {},
    "config_norms_order": ["catch_limit", "violation_ban"]
  }
}
```
