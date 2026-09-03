# Round 1 Norm Specification

## Policy
No fisher may catch more than 10% of the lake's current biomass in a single trip (minimum 1kg).

## Operationalization
Before each trip, a fisher calculates 10% of the lake's current weight, rounds down to the nearest kg, and sets that as their personal quota. They record the catch and report weekly to the community. If a fisher exceeds the quota, they must return the excess and receive a warning; repeat violations result in a temporary fishing ban.

## Rule Fragment Classification

### Fragment 1: Catch Limit (10% of stock, minimum 1kg)
**Shape:** `catch_constraint`

This fragment establishes a per-trip catch limit calculated as:
- Take 10% of the lake's current biomass at round start
- Round down to the nearest whole kg
- Apply a minimum of 1kg (i.e., if 10% < 1kg, the limit is 1kg)

**Decision Granularity Analysis:** This is a deterministic calculation based on current state (stock level). No new agent decision is required - the quota is calculated automatically before each trip. The agent simply decides effort; the constraint is applied after physics calculates raw catch. This fits perfectly within the existing harvest phase.

### Fragment 2: Graduated Sanction (warning then ban)
**Shape:** `graduated_sanction`

This fragment establishes escalating consequences:
- First violation: Excess is returned, agent receives a warning
- Second/repeat violations: Temporary fishing ban

**Decision Granularity Analysis:** The sanction is applied automatically based on violation history tracked by the mechanism. No new agent decision is required. The warning vs. ban determination is made deterministically by checking persistent state (prior violations). This is a stateful graduated sanction, not a new phase.

### Fragment 3: Recording and Reporting
**Shape:** `reporting_obligation` (partial)

The operationalization mentions recording catches and reporting weekly to the community. The simulation has no concept of elapsed time within a round or separate reporting actions. The logging portion is not implemented. The "excess must be returned" is already covered by the catch constraint capping the kept amount.

## Requirements

### R1: Percentage-based catch limit
**Text:** Each fisher's catch limit for a trip shall be calculated as max(1, floor(0.10 * stock_before_round)) kg.
**Clarity:** CLEAR - The policy states 10% of lake's current biomass, rounded down, minimum 1kg.

### R2: Excess returned on violation
**Text:** When a fisher's raw catch exceeds their calculated limit, the excess amount shall not be kept (i.e., only the limit amount is counted toward their harvested_kg).
**Clarity:** CLEAR - Operationalization states "return the excess".

### R3: Warning on first violation
**Text:** On a fisher's first violation of the catch limit, they shall receive a warning (recorded in their violation history) but shall not be banned from fishing.
**Clarity:** CLEAR - Operationalization states "receive a warning" before "repeat violations result in a temporary fishing ban".

### R4: Ban on repeat violations
**Text:** On a fisher's second or subsequent violation of the catch limit, they shall receive a temporary fishing ban of 1 trip.
**Clarity:** INCOMPLETE - The operationalization says "temporary fishing ban" but does not specify the ban duration in trips. Clarification needed.

**Clarification Question:** What is the duration of the temporary fishing ban for repeat violations? Is it one trip, multiple trips, or does it escalate?

## Implementation Plan

### Parametric Components
- `catch_limit` norm with `limit_pct_of_stock: 0.10` and `min_limit_kg: 1` parameter

### Structural Components  
- New `violation_tracker` norm type that:
  - Tracks violation count per agent in persistent state
  - Issues warnings on first violation (via NormDecision.violation with warning note)
  - Issues ban sanctions on second+ violations (via NormDecision.violation with "repeat_violation" sanction)
  - Config parameter for `ban_trips` (duration of ban)

### Enforcement Order
1. `catch_limit` - caps the catch at the calculated limit, emits "over_cap" sanction
2. `violation_tracker` - checks sanction, tracks violations, upgrades to ban sanction on repeat
3. `violation_ban` - handles the actual ban based on "repeat_violation" sanction from tracker

### Note on Reporting
The "record the catch and report weekly" portion of the operationalization is not implemented as the simulation lacks a model of weekly reporting or separate logging actions within/between rounds.

## Machine-Readable Summary

```json
{
  "round": 1,
  "policy": "No fisher may catch more than 10% of the lake's current biomass in a single trip (minimum 1kg).",
  "fragments": [
    {
      "id": "F1",
      "shape": "catch_constraint",
      "type": "parametric",
      "norm_type": "catch_limit",
      "parameters": {
        "limit_pct_of_stock": 0.10,
        "min_limit_kg": 1
      },
      "requirements": ["R1", "R2"]
    },
    {
      "id": "F2", 
      "shape": "graduated_sanction",
      "type": "structural",
      "norm_type": "violation_tracker",
      "parameters": {
        "trigger_sanction": "over_cap",
        "warning_first": true,
        "ban_after_violations": 2,
        "ban_trips": 1
      },
      "requirements": ["R3", "R4"]
    }
  ],
  "requirements": [
    {
      "id": "R1",
      "text": "Each fisher's catch limit for a trip shall be calculated as max(1, floor(0.10 * stock_before_round)) kg.",
      "clarity": "CLEAR",
      "testable": true
    },
    {
      "id": "R2",
      "text": "When a fisher's raw catch exceeds their calculated limit, the excess amount shall not be kept.",
      "clarity": "CLEAR",
      "testable": true
    },
    {
      "id": "R3",
      "text": "On a fisher's first violation of the catch limit, they shall receive a warning but shall not be banned from fishing.",
      "clarity": "CLEAR",
      "testable": true
    },
    {
      "id": "R4",
      "text": "On a fisher's second or subsequent violation of the catch limit, they shall receive a temporary fishing ban of 1 trip.",
      "clarity": "INCOMPLETE",
      "note": "Ban duration assumed to be 1 trip pending clarification",
      "testable": true
    }
  ],
  "phases_added": [],
  "institutional_changes": {
    "add_state": [],
    "add_fluents": []
  },
  "not_implemented": [
    "Weekly recording and reporting of catches (simulation lacks time/logging model)"
  ]
}
```
