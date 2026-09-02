# Round 2 Norm Specification

## Policy
Each fisher may take up to 12.5% of the lake's current fish biomass per trip, with a minimum catch of 1kg to ensure survival.

## Operationalization
Before each trip, a community steward will announce the lake biomass. Each fisher must declare their intended catch; if it exceeds 12.5% of the biomass, they must reduce their catch or pay a penalty equal to 50% of the overage to the community. Violations will result in a temporary fishing ban after three infractions. All catches are logged and reviewed quarterly to adjust quotas if the lake biomass falls below 200kg.

## Requirements

### R1: Per-trip catch limit (percentage-based)
- **Text**: Each fisher's kept catch shall not exceed 12.5% of the current lake biomass.
- **Classification**: catch_constraint
- **Clarity**: CLEAR
- **Test**: `harvested_kg(agent, trip) <= 0.125 * stock_before`

### R2: Excess release
- **Text**: Any catch amount above the 12.5% limit must be released (not kept).
- **Classification**: catch_constraint
- **Clarity**: CLEAR
- **Test**: If `raw_kg > 0.125 * stock`, then `kept_kg <= 0.125 * stock`

### R3: Penalty for overage
- **Text**: Fishers who exceed the 12.5% limit must pay a penalty equal to 50% of the overage to the community.
- **Classification**: financial_penalty
- **Clarity**: CLEAR
- **Test**: If `raw_kg > limit`, then `penalty = 0.5 * (raw_kg - limit)` and `final_kept = limit - penalty`, with penalty added to community fund

### R4: Three-strike ban system
- **Text**: A fisher who exceeds the limit three times receives a temporary fishing ban.
- **Classification**: graduated_sanction
- **Clarity**: CLEAR
- **Note**: The operationalization mentions "temporary" but doesn't specify duration; default to 2 trips (1 trip would be very short given the 3-violation threshold).
- **Test**: After 3 violations with sanction "over_cap", `is_eligible(agent)` returns False for 2 subsequent rounds

### R5: Quarterly biomass review (acknowledged)
- **Text**: Catches are reviewed quarterly and quotas adjusted if biomass < 200kg.
- **Classification**: governance_procedure
- **Clarity**: INCOMPLETE
- **Note**: The quarterly review and quota adjustment mechanism is not directly operationalizable without defining the specific adjustment rule. The biomass threshold monitoring could be implemented, but the actual quota adjustment action is underspecified. The core enforcement (12.5% limit + penalty + 3-strike ban) is captured in R1-R4.

### R6: Steward announcement (acknowledged)
- **Text**: A community steward announces lake biomass before each trip.
- **Classification**: reporting_obligation
- **Clarity**: INCOMPLETE
- **Note**: The steward role and announcement process is not operationalizable as a distinct phase. The biomass information is already available to all agents through the simulation context.

### R7: Minimum catch of 1kg (acknowledged)
- **Text**: Fishers must have a minimum catch of 1kg to ensure survival.
- **Classification**: catch_constraint
- **Clarity**: INCOMPLETE
- **Note**: The policy mentions this as a requirement, but the operationalization does not specify enforcement (what happens if someone would catch less than 1kg?). In practice, with typical stock levels and physics, this is unlikely to bind. The 12.5% limit and penalty system are the primary operational constraints.

## Implementation Summary

| Fragment | Shape | Parameters | Owner | Verification |
|----------|-------|------------|-------|--------------|
| 12.5% catch limit | catch_constraint | limit_pct_of_stock: 0.125 | norms/catch_limit.py (catch_limit) | tests/norms/test_catch_limit.py |
| Release excess | catch_constraint | (implicit in limit) | norms/catch_limit.py (catch_limit) | tests/norms/test_catch_limit.py |
| 50% overage penalty | financial_penalty | penalty_pct: 0.5, target: "community_fund" | norms/overage_penalty.py (overage_penalty) | tests/norms/test_overage_penalty.py |
| Three-strike ban | graduated_sanction | trigger_sanction: "over_cap", strikes: 3, ban_trips: 2 | norms/strike_ban.py (strike_ban) | tests/norms/test_strike_ban.py |

## Classification

This norm is **partially parametric, partially new plugin**:
- Uses existing `catch_limit` norm type for the 12.5% limit (parametric)
- Requires new `overage_penalty` norm type for the 50% penalty on overages
- Requires new `strike_ban` norm type for the three-strike ban system

## Config Changes Required

```json
{
  "norms": [
    {"type": "catch_limit", "id": "catch_limit", "limit_pct_of_stock": 0.125},
    {"type": "overage_penalty", "id": "overage_penalty", "penalty_pct": 0.5, "target_fund": "community_fund"},
    {"type": "strike_ban", "id": "strike_ban", "trigger_sanction": "over_cap", "strikes": 3, "ban_trips": 2}
  ]
}
```

## Notes

- Order matters: `catch_limit` → `overage_penalty` → `strike_ban`
  - `catch_limit` generates the "over_cap" sanction
  - `overage_penalty` calculates and deducts the penalty from kept_kg
  - `strike_ban` counts violations and enforces the ban after 3 strikes
- The "community_fund" referenced by overage_penalty is a shared pool; the actual distribution mechanism is out of scope for this round.
- The penalty calculation: if a fisher catches X kg over the limit L, they pay 0.5 * (X - L) to the community, leaving them with L - 0.5 * (X - L) = 1.5*L - 0.5*X kg.
- Strike counts persist across rounds and are tracked per-agent in norm state.

```json
{
  "round": 2,
  "classification": [
    {"rule": "12.5% catch limit", "shape": "catch_constraint", "parametric": true, "owner": "norms/catch_limit.py", "verification": "tests/norms/test_catch_limit.py"},
    {"rule": "50% overage penalty", "shape": "financial_penalty", "parametric": false, "owner": "norms/overage_penalty.py", "verification": "tests/norms/test_overage_penalty.py"},
    {"rule": "3-strike ban", "shape": "graduated_sanction", "parametric": false, "owner": "norms/strike_ban.py", "verification": "tests/norms/test_strike_ban.py"}
  ],
  "phases_added": [],
  "requires_new_plugin": true,
  "clarifications_needed": 0
}
```
