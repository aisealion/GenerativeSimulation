# Round 2 Norm Specification

## Policy
No fisher may take more than 8% of the lake's current biomass per trip, and the lake must retain a minimum of 180kg at all times.

## Operationalization
Each fisher records their catch weight in a shared logbook by 6pm the same day. The community reviews the log weekly, ensuring no one exceeded the 8% limit and that the lake's total remains above 180kg. Violations incur a community fee equal to the excess weight and, if repeated, a one‑trip suspension. The rule is re‑evaluated every quarter.

## Rule Fragments and Classification

### Fragment 1: 8% Per-Trip Catch Limit
- **Shape**: `catch_constraint`
- **Description**: Each fisher's catch is capped at 8% of the lake's current biomass per trip
- **Rationale**: This is a percentage-based individual catch limit. The existing `catch_limit` plugin already supports `limit_pct_of_stock` parameter.

**Requirements:**
- **R1**: `harvested_kg(agent, trip) <= 0.08 * stock_before` for every fisher on every trip
- **Clarity**: CLEAR - the 8% limit is explicitly stated
- **R2**: Excess catch above the 8% limit is not kept
- **Clarity**: CLEAR - implied by "no fisher may take more than"

### Fragment 2: Minimum Stock Floor (180kg)
- **Shape**: `stock_constraint`
- **Description**: The lake must never drop below 180kg total biomass
- **Rationale**: This is a hard floor on the lake's stock level. Unlike a community cap that limits catch, this constrains fishing based on what would remain. No existing plugin provides this functionality — it's a structural gap.

**Requirements:**
- **R3**: `stock_after_harvest >= 180kg` must hold at all times
- **Clarity**: CLEAR - the 180kg minimum is explicitly stated
- **R4**: If a fisher's catch would push stock below 180kg, their catch must be reduced or prevented
- **Clarity**: AMBIGUOUS - the operationalization doesn't specify *how* to enforce this (proportional reduction? First-come-first-served? Complete shutdown?)

### Fragment 3: Shared Logbook Recording by 6pm
- **Shape**: `reporting_obligation`
- **Description**: Fishers must record their catch in a shared logbook by 6pm same day
- **Rationale**: This is a procedural requirement about documentation and timing. The simulation already records all catches in `state/runtime.json`, so the "shared logbook" exists. However, there is no time-of-day model.

**Requirements:**
- **R5**: All catches are recorded in a shared log
- **Clarity**: CLEAR - already implemented by the simulation's runtime tracking
- **R6**: Recording must happen by 6pm the same day
- **Clarity**: TECHNICALLY_UNREALIZABLE - the simulation operates in discrete rounds without intra-round time or deadlines

### Fragment 4: Weekly Community Review
- **Shape**: `monitoring_procedure`
- **Description**: The community reviews the log weekly to verify compliance
- **Rationale**: This describes a verification cadence. The simulation checks norms every round; there's no "weekly" concept as rounds are the atomic time unit.

**Requirements:**
- **R7**: Compliance with the 8% limit is verified
- **Clarity**: CLEAR - enforced every round by the norm plugin
- **R8**: Compliance with the 180kg minimum is verified
- **Clarity**: CLEAR - enforced every round by the norm plugin
- **R9**: Review happens on a weekly schedule
- **Clarity**: TECHNICALLY_UNREALIZABLE - the simulation has no calendar/time model beyond sequential rounds

### Fragment 5: Community Fee for Violations
- **Shape**: `financial_sanction`
- **Description**: Violators pay a community fee equal to the excess weight caught
- **Rationale**: This is a monetary penalty tied to violation magnitude. The simulation tracks `payoff` (cumulative fish value) per agent but has no separate "money" or "fee" mechanism. A fee could be modeled as reducing the violator's payoff.

**Requirements:**
- **R10**: A fisher who exceeds the 8% limit pays a fee equal to the excess kg
- **Clarity**: CLEAR - "community fee equal to the excess weight"
- **R11**: The fee is deducted from the violator's accumulated payoff
- **Clarity**: AMBIGUOUS - no explicit currency/payoff deduction mechanism exists; need to determine if this reduces harvested value or is a separate penalty

### Fragment 6: One-Trip Suspension for Repeated Violations
- **Shape**: `graduated_sanction`
- **Description**: Repeated violations result in a one-trip fishing ban
- **Rationale**: This is a punitive ban triggered by multiple violations. The existing `violation_ban` plugin supports this pattern.

**Requirements:**
- **R12**: A fisher who violates twice receives a one-trip ban
- **Clarity**: CLEAR - "if repeated, a one‑trip suspension"
- **R13**: The ban lasts exactly one trip (round)
- **Clarity**: CLEAR - "one‑trip suspension"

### Fragment 7: Quarterly Re-evaluation
- **Shape**: `meta_rule`
- **Description**: The rule is re-evaluated every quarter
- **Rationale**: This describes the norm's own lifecycle, not harvest-time enforcement. The simulation's norm negotiation mechanism already handles re-evaluation, but not on a calendar schedule.

**Requirements:**
- **R14**: The norm may be revised or replaced periodically
- **Clarity**: CLEAR - handled by the simulation's existing propose/vote/implement cycle
- **R15**: Re-evaluation occurs quarterly
- **Clarity**: TECHNICALLY_UNREALIZABLE - no calendar model; the community can propose changes any round

## Clarification Exchange

None required — the ambiguities below are resolved by architectural constraints, not proposer intent.

### Resolution for R4 (Enforcement Method for 180kg Floor)
Given the lack of explicit guidance in the operationalization, we interpret this as: **the harvest phase must ensure no individual catch reduces the lake below 180kg**. The simplest implementation is a proportional reduction: if total demand would violate the floor, each fisher's allowed catch is scaled down proportionally. Alternatively, first-come-first-served (earlier fishers in iteration order get priority) is also valid. Given the existing `community_cap` uses first-come-first-served, we adopt the same pattern for consistency: fishers are processed in order, and once the 180kg floor would be breached, subsequent fishers receive 0kg.

### Resolution for R11 (Fee Mechanism)
The simulation's `payoff` field represents cumulative value from fish. We interpret the "community fee" as: **the excess weight (above 8%) does not contribute to the violator's payoff**. This is naturally enforced by the `catch_limit` plugin — the excess is never "kept" and therefore never adds to payoff. No separate deduction mechanism is needed.

## Implementation Plan

| Fragment | Shape | Parametric | Owner | Verification |
|----------|-------|------------|-------|--------------|
| 8% per-trip limit | catch_constraint | Yes | `norms/catch_limit.py` (type: `catch_limit`) | `tests/norm_evaluation/round_2/test_catch_limit.py` |
| 180kg stock floor | stock_constraint | No | **NEW** `norms/stock_floor.py` (type: `stock_floor`) | `tests/norm_evaluation/round_2/test_stock_floor.py` |
| One-trip suspension for repeats | graduated_sanction | Yes | `norms/violation_ban.py` (type: `violation_ban`) | `tests/norm_evaluation/round_2/test_violation_tracking.py` |

### Structural Changes Required

1. **New norm plugin**: `norms/stock_floor.py` — implements the 180kg minimum stock floor using first-come-first-served enforcement.

2. **Violations tracking**: The `violation_ban` plugin needs to count violations per agent across rounds. Currently it only tracks ban duration, not violation count. The `stock_floor` norm must emit a sanction when it blocks/reduces a catch due to the floor.

### Configuration

The norm will be implemented via:
1. A new `stock_floor` plugin file
2. Updated configuration in `state/config.json`:

```json
{
  "norms": [
    {"type": "catch_limit", "limit_pct_of_stock": 0.08},
    {"type": "stock_floor", "min_stock_kg": 180},
    {"type": "violation_ban", "trigger_sanction": ["over_cap", "below_floor"], "trips": 1}
  ]
}
```

Notes:
- `catch_limit` comes first to enforce individual percentage caps
- `stock_floor` comes second to enforce the aggregate floor constraint
- `violation_ban` comes last to apply one-trip bans for repeated violations
- The `trigger_sanction` list includes `"over_cap"` (from catch_limit) and `"below_floor"` (from stock_floor)
- `trips: 1` implements the "one‑trip suspension"

## Fourth-Wall Compliance

All enforcement happens through norm plugins with `describe()` methods that provide in-world explanations. No internal state keys or code terms appear in agent-facing text.

## Machine-Readable Summary

```json
{
  "round": 2,
  "policy": "No fisher may take more than 8% of the lake's current biomass per trip, and the lake must retain a minimum of 180kg at all times.",
  "classification": [
    {
      "fragment": "8% per-trip limit",
      "shape": "catch_constraint",
      "parametric": true,
      "owner": "norms/catch_limit.py (catch_limit)",
      "verification": "tests/norm_evaluation/round_2/test_catch_limit.py"
    },
    {
      "fragment": "180kg stock floor",
      "shape": "stock_constraint",
      "parametric": false,
      "owner": "norms/stock_floor.py (stock_floor)",
      "verification": "tests/norm_evaluation/round_2/test_stock_floor.py"
    },
    {
      "fragment": "One-trip suspension for repeats",
      "shape": "graduated_sanction",
      "parametric": true,
      "owner": "norms/violation_ban.py (violation_ban)",
      "verification": "tests/norm_evaluation/round_2/test_violation_tracking.py"
    }
  ],
  "requirements": [
    {"id": "R1", "text": "harvested_kg(agent, trip) <= 0.08 * stock_before for every fisher on every trip", "clarity": "CLEAR"},
    {"id": "R2", "text": "Excess catch above the 8% limit is not kept", "clarity": "CLEAR"},
    {"id": "R3", "text": "stock_after_harvest >= 180kg must hold at all times", "clarity": "CLEAR"},
    {"id": "R4", "text": "If a fisher's catch would push stock below 180kg, their catch must be reduced or prevented", "clarity": "AMBIGUOUS", "resolution": "First-come-first-served enforcement: process fishers in order, stop when floor would be breached"},
    {"id": "R5", "text": "All catches are recorded in a shared log", "clarity": "CLEAR"},
    {"id": "R6", "text": "Recording must happen by 6pm the same day", "clarity": "TECHNICALLY_UNREALIZABLE"},
    {"id": "R7", "text": "Compliance with the 8% limit is verified", "clarity": "CLEAR"},
    {"id": "R8", "text": "Compliance with the 180kg minimum is verified", "clarity": "CLEAR"},
    {"id": "R9", "text": "Review happens on a weekly schedule", "clarity": "TECHNICALLY_UNREALIZABLE"},
    {"id": "R10", "text": "A fisher who exceeds the 8% limit pays a fee equal to the excess kg", "clarity": "CLEAR"},
    {"id": "R11", "text": "The fee is deducted from the violator's accumulated payoff", "clarity": "AMBIGUOUS", "resolution": "Excess weight is never kept, so never adds to payoff — no separate deduction needed"},
    {"id": "R12", "text": "A fisher who violates twice receives a one-trip ban", "clarity": "CLEAR"},
    {"id": "R13", "text": "The ban lasts exactly one trip (round)", "clarity": "CLEAR"},
    {"id": "R14", "text": "The norm may be revised or replaced periodically", "clarity": "CLEAR"},
    {"id": "R15", "text": "Re-evaluation occurs quarterly", "clarity": "TECHNICALLY_UNREALIZABLE"}
  ],
  "config_changes": {
    "state/config.json": {
      "norms": [
        {"type": "catch_limit", "limit_pct_of_stock": 0.08},
        {"type": "stock_floor", "min_stock_kg": 180},
        {"type": "violation_ban", "trigger_sanction": ["over_cap", "below_floor"], "trips": 1}
      ]
    }
  },
  "new_phase": false,
  "structural_changes": true,
  "structural_details": {
    "new_files": ["norms/stock_floor.py"],
    "modified_files": ["state/config.json"]
  }
}
```
