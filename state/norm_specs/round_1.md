# Round 1 Norm Specification

## Policy
Each fisherman may keep up to 10 kg of fish per trip; any catch beyond 10 kg must be released back into the lake.

## Operationalization
All catch amounts are written on the community ledger at the end of each trip. If a fisher exceeds the 10 kg limit, they must immediately release the excess fish and mark it as 'released' on the ledger. Failure to record or to release excess fish results in a temporary fishing ban for the next trip. A rotating overseer checks the ledger weekly and issues the ban if necessary.

## Requirements

### R1: Per-trip catch limit
- **Text**: Each fisher's kept catch for a single trip shall not exceed 10 kg.
- **Classification**: catch_constraint
- **Clarity**: CLEAR
- **Test**: `harvested_kg(agent, trip) <= 10.0`

### R2: Excess release
- **Text**: Any catch amount above 10 kg must be released (not kept).
- **Classification**: catch_constraint
- **Clarity**: CLEAR
- **Test**: If `raw_kg > 10.0`, then `kept_kg == 10.0` and released amount == `raw_kg - 10.0`

### R3: Violation sanction - temporary ban
- **Text**: A fisher who exceeds the 10 kg limit receives a temporary fishing ban for exactly 1 subsequent trip.
- **Classification**: graduated_sanction
- **Clarity**: CLEAR
- **Note**: The operationalization mentions "next trip" which maps to 1 trip ban length.
- **Test**: After a violation, `is_eligible(agent)` returns False for exactly 1 subsequent round, then True again.

### R4: Ledger recording (acknowledged)
- **Text**: Catch amounts are recorded on a community ledger.
- **Classification**: reporting_obligation
- **Clarity**: INCOMPLETE
- **Note**: The simulation does not model a separate reporting action or ledger verification process. The harvest outcome is automatically recorded in runtime["rounds"]. The ledger/checking mechanism described is not operationalizable as a distinct phase. The operationalizable core (10kg limit + ban for violation) is captured in R1-R3.

### R5: Rotating overseer (acknowledged)
- **Text**: A rotating overseer checks the ledger weekly and issues bans.
- **Classification**: role_fluent
- **Clarity**: INCOMPLETE
- **Note**: The overseer role and weekly checking process is not operationalizable without a new phase for overseer decisions. The ban enforcement itself is automatic via the violation_ban norm plugin, which achieves the same outcome (ban for violation) without requiring a separate overseer role.

## Implementation Summary

| Fragment | Shape | Parameters | Owner | Verification |
|----------|-------|------------|-------|--------------|
| 10kg catch limit | catch_constraint | limit_kg: 10 | norms/catch_limit.py (catch_limit) | tests/regression/test_catch_limit.py |
| Release excess | catch_constraint | (implicit in limit) | norms/catch_limit.py (catch_limit) | tests/regression/test_catch_limit.py |
| Temporary ban | graduated_sanction | trigger_sanction: "over_cap", trips: 1 | norms/violation_ban.py (violation_ban) | tests/regression/test_violation_ban.py |

## Classification

This norm is **parametric** — it uses existing `catch_limit` and `violation_ban` norm types with specific parameter values (10kg limit, 1-trip ban).

## Config Changes Required

```json
{
  "norms": [
    {"type": "catch_limit", "id": "catch_limit", "limit_kg": 10},
    {"type": "violation_ban", "id": "violation_ban", "trigger_sanction": "over_cap", "trips": 1}
  ]
}
```

## Notes

- The "ledger" and "rotating overseer" aspects of the operationalization are not directly implementable without adding new phases. The core enforcement (10kg limit + automatic ban) is achievable with existing plugins.
- Order matters: `catch_limit` must come before `violation_ban` in the config so the sanction is generated before the ban norm checks for it.
- The sanction string "over_cap" is the default emitted by `CatchLimitNorm` when the limit is exceeded.

```json
{
  "round": 1,
  "classification": [
    {"rule": "10kg catch limit", "shape": "catch_constraint", "parametric": true, "owner": "norms/catch_limit.py", "verification": "tests/norms/test_catch_limit.py"},
    {"rule": "1-trip ban for violation", "shape": "graduated_sanction", "parametric": true, "owner": "norms/violation_ban.py", "verification": "tests/norms/test_violation_ban.py"}
  ],
  "phases_added": [],
  "requires_new_plugin": false,
  "clarifications_needed": 0
}
```
