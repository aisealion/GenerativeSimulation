# Round 2 Norm Specification

## Policy
Each fisher may harvest no more than 20% of the lake's current stock per trip, and we must preserve at least a 10% reserve of the current stock at all times.

## Operationalization
Before each trip the fisher records the lake's current stock. They may take up to 20% of that amount. The community fishery committee—Miro, Kai, Mara, Toa, Rina, Beti, Solo, Lani, Nadia, Tevita—will verify the log and weigh the catch. If a fisher exceeds 20% or leaves less than 10% of the stock, they must return the excess to the community pool. The committee meets monthly to recalculate the stock, adjust individual quotas, and impose a temporary fishing ban on violators until they comply.

## Rule Fragment Classification

| Fragment | Shape | Parameters | Owner | Verification |
|----------|-------|------------|-------|--------------|
| Per-fisher 20% limit | catch_constraint | limit_pct_of_stock: 0.20 | norms/catch_limit.py (catch_limit) | tests/norm_checks/test_round_2.py |
| 10% minimum stock reserve | catch_constraint | cap_pct_of_stock: 0.90 | norms/community_cap.py (community_cap) | tests/norm_checks/test_round_2.py |
| Ban for violations | graduated_sanction | trigger_sanction: "over_cap", trips: 1 | norms/violation_ban.py (violation_ban) | tests/norm_checks/test_round_2.py |

## Requirements

### R1: Per-Fisher Percentage-Based Catch Limit
- **Text**: Each fisher may keep at most 20% of the lake's current stock from any single trip.
- **Clarity**: CLEAR
- **Testable Condition**: For any harvest phase, `harvested_kg(agent) <= 0.20 * stock_before` for all agents.

### R2: Surplus Return on Individual Limit Violation
- **Text**: If a fisher's raw catch exceeds 20% of current stock, the surplus (amount over 20%) is not kept and the violation is flagged.
- **Clarity**: CLEAR
- **Testable Condition**: If `raw_kg > 0.20 * stock_before`, then `kept_kg = 0.20 * stock_before` and the decision carries sanction "over_cap".

### R3: Minimum Stock Reserve (Community-Wide)
- **Text**: The community's total catch in a round cannot exceed 90% of the lake's stock at the start of that round (ensuring at least 10% remains).
- **Clarity**: CLEAR
- **Testable Condition**: `sum(harvested_kg) <= 0.90 * stock_kg_before` for the round.

### R4: Reserve Enforcement Order
- **Text**: The community reserve cap is enforced first-come-first-served based on agent iteration order.
- **Clarity**: CLEAR
- **Testable Condition**: Once the running tally reaches 90% of stock, subsequent agents in that round receive `kept_kg = 0` with sanction "over_community_cap".

### R5: One-Round Ban for Violations
- **Text**: A fisher who exceeds the 20% limit or causes the stock to fall below 10% is barred from fishing in the next round.
- **Clarity**: CLEAR
- **Testable Condition**: If an agent's decision in round N has sanction "over_cap" or "over_community_cap", then in round N+1, `is_eligible(agent) = False`.

### R6: Committee Verification (Partial Implementation)
- **Text**: The community fishery committee verifies the log and weighs the catch.
- **Clarity**: INCOMPLETE
- **Note**: The operationalization describes a committee verification process, but the simulation architecture has no model of independent verification or weighing by a separate committee. The committee names listed (Miro, Kai, Mara, Toa, Rina, Beti, Solo, Lani, Nadia, Tevita) appear to be the same fishers in the simulation roster, not distinct verification roles. The core protective constraints (20% individual cap and 10% minimum stock) are operationalized via the catch_limit and community_cap plugins.

### R7: Monthly Committee Review (Not Implemented)
- **Text**: The committee meets monthly to recalculate the stock, adjust individual quotas, and impose sanctions.
- **Clarity**: INCOMPLETE
- **Note**: The "monthly" timeframe and "quota adjustment" decision process describe a deliberative mechanism not present in the simulation architecture. Stock is recalculated automatically each round via regrowth physics. The sanction mechanism is automated via violation_ban rather than a committee decision.

## Implementation Notes

### Config Order
The norms in `state["config"]["norms"]` must be ordered as:
1. `catch_limit` (individual 20% cap) - evaluates individual violations first
2. `community_cap` (90% community cap to preserve 10% reserve) - tracks running total after individual caps
3. `violation_ban` (ban enforcement) - activates on "over_cap" or "over_community_cap" sanction

This ordering ensures:
- Individual percentage caps are applied and violations flagged before community tally
- Community cap sees the post-cap amounts when computing its running total
- Ban is triggered by violations from either cap norm

### No New Phase Required
All rule fragments are deterministic constraints on harvest quantities and consequences. No agent decision beyond the existing harvest phase is required. The "committee verification" and "monthly review" language in the operationalization describes aspirational governance processes that cannot be directly operationalized in the current architecture.

### No Structural Changes Required
All fragments can be implemented using existing norm plugins:
- `catch_limit` for the 20% per-fisher cap (using `limit_pct_of_stock` parameter)
- `violation_ban` for the one-round fishing ban
- `community_cap` for the 90% community catch limit (to preserve 10% reserve)

## Machine-Readable Summary

```json
{
  "round": 2,
  "policy": "Each fisher may harvest no more than 20% of the lake's current stock per trip, and we must preserve at least a 10% reserve of the current stock at all times",
  "fragments": [
    {
      "id": "F1",
      "shape": "catch_constraint",
      "parametric": true,
      "type": "catch_limit",
      "config": {"type": "catch_limit", "limit_pct_of_stock": 0.20}
    },
    {
      "id": "F2",
      "shape": "catch_constraint",
      "parametric": true,
      "type": "community_cap",
      "config": {"type": "community_cap", "cap_pct_of_stock": 0.90}
    },
    {
      "id": "F3",
      "shape": "graduated_sanction",
      "parametric": true,
      "type": "violation_ban",
      "config": {"type": "violation_ban", "trigger_sanction": "over_cap", "trips": 1}
    }
  ],
  "requirements": [
    {"id": "R1", "clarity": "CLEAR", "fragment": "F1"},
    {"id": "R2", "clarity": "CLEAR", "fragment": "F1"},
    {"id": "R3", "clarity": "CLEAR", "fragment": "F2"},
    {"id": "R4", "clarity": "CLEAR", "fragment": "F2"},
    {"id": "R5", "clarity": "CLEAR", "fragment": "F3"},
    {"id": "R6", "clarity": "INCOMPLETE", "fragment": null, "note": "Committee verification process not operationalizable in current architecture"},
    {"id": "R7", "clarity": "INCOMPLETE", "fragment": null, "note": "Monthly committee review process not operationalizable in current architecture"}
  ],
  "institutional_changes": {
    "add_phases": [],
    "add_state": {},
    "config_norms_order": ["catch_limit", "community_cap", "violation_ban"]
  }
}
```
