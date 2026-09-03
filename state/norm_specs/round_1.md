# Round 1 Norm Specification

## Policy
Each fisher may take up to 15kg per trip and the community's total catch per day must not exceed 100kg.

## Operationalization
Every fisher writes their catch on a communal ledger at the dock. A community steward checks the ledger each day; if a fisher's catch exceeds 15kg, the excess must be returned or the fisher forfeits that day's rights. If the total daily catch exceeds 100kg, the remaining fishers must cease fishing that day. Non-compliance results in a temporary fishing ban for the offending fisher.

## Rule Fragments and Classification

### Fragment 1: Individual Catch Limit
- **Shape**: `catch_constraint`
- **Description**: Each fisher's catch is capped at 15kg per trip
- **Rationale**: This is a straightforward per-agent numeric limit on harvest output. No new decisions required—it's enforced deterministically during the harvest phase.

**Requirements:**
- **R1**: `harvested_kg(agent, trip) <= 15` for every fisher on every trip
- **Clarity**: CLEAR - the 15kg limit is explicitly stated
- **R2**: Excess catch above 15kg is not kept (returned/rejected)
- **Clarity**: CLEAR - operationalization says "excess must be returned"

### Fragment 2: Community Catch Limit
- **Shape**: `catch_constraint`
- **Description**: Total community catch across all fishers in a round must not exceed 100kg
- **Rationale**: This is a community-level aggregate constraint. The "remaining fishers must cease" language describes first-come-first-served enforcement, which is deterministically enforceable during harvest.

**Requirements:**
- **R3**: `sum(harvested_kg(all_agents, round)) <= 100` for each round
- **Clarity**: CLEAR - the 100kg limit is explicitly stated
- **R4**: When the community cap is reached, subsequent fishers in the same round receive 0kg
- **Clarity**: CLEAR - "remaining fishers must cease fishing that day"

### Fragment 3: Non-Compliance Ban
- **Shape**: `graduated_sanction`
- **Description**: Fishers who violate either limit are temporarily banned from fishing
- **Rationale**: A punitive consequence triggered by violations of R1/R2 or R3/R4. The operationalization specifies a ban but doesn't specify duration—this is the key ambiguity.

**Requirements:**
- **R5**: A fisher who exceeds the 15kg individual limit receives a temporary fishing ban
- **Clarity**: CLEAR - the ban is explicitly stated, but duration is not specified
- **R6**: A fisher who catches when the community cap is already exhausted receives a temporary fishing ban
- **Clarity**: CLEAR - same as R5
- **R7**: The ban duration must be specified (operationalization says "temporary" but gives no number)
- **Clarity**: INCOMPLETE - duration of "temporary" ban not specified

## Clarification Exchange

**Question 1**: The operationalization states that non-compliance results in a "temporary fishing ban" but doesn't specify how many trips the ban should last. Is this meant to be a single-trip ban, a multi-trip ban (e.g., 2 or 3 trips), or should it last until some other condition is met?

**Resolution**: For this implementation, we interpret "temporary" as a **2-trip ban** following the pattern established in the violation_ban plugin's default behavior. This is a reasonable middle ground between a single trip (possibly too lenient) and a longer ban (possibly too harsh for initial norms).

## Implementation Plan

| Fragment | Shape | Parametric | Owner | Verification |
|----------|-------|------------|-------|--------------|
| Individual 15kg limit | catch_constraint | Yes | `norms/catch_limit.py` (type: `catch_limit`) | `tests/norm_checks/test_round_1_limits.py` |
| Community 100kg limit | catch_constraint | Yes | `norms/community_cap.py` (type: `community_cap`) | `tests/norm_checks/test_round_1_limits.py` |
| 2-trip ban for violations | graduated_sanction | Yes | `norms/violation_ban.py` (type: `violation_ban`) | `tests/norm_checks/test_round_1_limits.py` |

## Configuration

The norm will be implemented via pure configuration in `state/config.json`:

```json
{
  "norms": [
    {"type": "catch_limit", "limit_kg": 15},
    {"type": "community_cap", "cap_kg": 100},
    {"type": "violation_ban", "trigger_sanction": ["over_cap", "over_community_cap"], "trips": 2}
  ]
}
```

Notes:
- `catch_limit` comes first to enforce individual caps
- `community_cap` comes second to enforce the aggregate limit
- `violation_ban` comes last to catch sanctions from either of the above
- The `trigger_sanction` list includes both `"over_cap"` (emitted by `catch_limit` when limit exceeded) and `"over_community_cap"` (emitted by `community_cap` when cap exhausted)

## Fourth-Wall Compliance

All enforcement happens through norm plugins with `describe()` methods that provide in-world explanations. No internal state keys or code terms appear in agent-facing text.

## Machine-Readable Summary

```json
{
  "round": 1,
  "policy": "Each fisher may take up to 15kg per trip and the community's total catch per day must not exceed 100kg.",
  "classification": [
    {
      "fragment": "Individual 15kg limit",
      "shape": "catch_constraint",
      "parametric": true,
      "owner": "norms/catch_limit.py (catch_limit)",
      "verification": "tests/norm_checks/test_round_1_limits.py"
    },
    {
      "fragment": "Community 100kg limit",
      "shape": "catch_constraint",
      "parametric": true,
      "owner": "norms/community_cap.py (community_cap)",
      "verification": "tests/norm_checks/test_round_1_limits.py"
    },
    {
      "fragment": "2-trip ban for violations",
      "shape": "graduated_sanction",
      "parametric": true,
      "owner": "norms/violation_ban.py (violation_ban)",
      "verification": "tests/norm_checks/test_round_1_limits.py"
    }
  ],
  "requirements": [
    {"id": "R1", "text": "harvested_kg(agent, trip) <= 15 for every fisher on every trip", "clarity": "CLEAR"},
    {"id": "R2", "text": "Excess catch above 15kg is not kept (returned/rejected)", "clarity": "CLEAR"},
    {"id": "R3", "text": "sum(harvested_kg(all_agents, round)) <= 100 for each round", "clarity": "CLEAR"},
    {"id": "R4", "text": "When the community cap is reached, subsequent fishers in the same round receive 0kg", "clarity": "CLEAR"},
    {"id": "R5", "text": "A fisher who exceeds the 15kg individual limit receives a temporary fishing ban", "clarity": "CLEAR"},
    {"id": "R6", "text": "A fisher who catches when the community cap is already exhausted receives a temporary fishing ban", "clarity": "CLEAR"},
    {"id": "R7", "text": "The ban duration is 2 trips", "clarity": "INCOMPLETE", "resolution": "Interpreted as 2 trips based on violation_ban default pattern"}
  ],
  "config_changes": {
    "state/config.json": {
      "norms": [
        {"type": "catch_limit", "limit_kg": 15},
        {"type": "community_cap", "cap_kg": 100},
        {"type": "violation_ban", "trigger_sanction": ["over_cap", "over_community_cap"], "trips": 2}
      ]
    }
  },
  "new_phase": false,
  "structural_changes": false
}
```
