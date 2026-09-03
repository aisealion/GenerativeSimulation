# Round 3 Norm Specification

## Policy
Each fisher may take up to 12% of the lake's current weight per trip, and must deposit 10% of their catch into a communal reserve that is used only for lake replenishment and to support fishers whose reserves fall below 5 kg.

## Operationalization
Before each trip, the fisher computes 12% of the lake's current weight and caps their catch at that amount. They set aside 10% of the actual catch into a communal ledger; any excess beyond the 12% cap must be allocated entirely to the reserve. The reserve is replenished only when the lake's weight falls below 100 kg. Compliance is verified by the community chair after each round; a fisher who fails to deposit the required 10% will have their next quota reduced to 6% of lake weight until they catch up.

## Requirements

### R1: Per-trip catch limit (percentage-based)
- **Text**: Each fisher's kept catch shall not exceed 12% of the current lake weight.
- **Classification**: catch_constraint
- **Clarity**: CLEAR
- **Test**: `harvested_kg(agent, trip) <= 0.12 * stock_before`

### R2: 10% communal reserve deposit
- **Text**: Each fisher must deposit 10% of their actual catch into a communal reserve.
- **Classification**: financial_obligation
- **Clarity**: CLEAR
- **Test**: For each agent, `deposit = 0.10 * kept_kg` and this amount is deducted from final payoff and added to communal reserve balance

### R3: Excess allocation to reserve
- **Text**: Any catch amount above the 12% limit must be allocated entirely to the reserve.
- **Classification**: catch_constraint
- **Clarity**: CLEAR
- **Test**: If `raw_kg > 0.12 * stock`, then `excess = raw_kg - 0.12 * stock` goes to reserve (in addition to the 10% deposit from kept amount)

### R4: Reserve used for lake replenishment
- **Text**: The reserve is used for lake replenishment when lake weight falls below 100 kg.
- **Classification**: replenishment_rule
- **Clarity**: CLEAR
- **Test**: If `stock_kg < 100`, then reserve balance is added to stock (lake replenishment), and reserve balance resets to 0

### R5: Reserve used to support fishers below 5 kg
- **Text**: The reserve supports fishers whose reserves fall below 5 kg.
- **Classification**: social_safety_net
- **Clarity**: INCOMPLETE
- **Note**: The term "reserves" here is ambiguous - does it mean personal food reserves (payoff balance)? The operationalization says the reserve is "used only for lake replenishment and to support fishers whose reserves fall below 5 kg". This suggests a withdrawal mechanism for fishers with low personal reserves. However, without a clear definition of "personal reserves" in the simulation context and how the support amount is determined, this requirement is underspecified. The core operationalizable constraints (R1-R4) are captured.

### R6: Community chair compliance verification
- **Text**: Compliance is verified by the community chair after each round.
- **Classification**: governance_procedure
- **Clarity**: INCOMPLETE
- **Note**: The community chair role and verification process are not operationalizable without a new phase for chair decisions. The compliance check itself (whether 10% was deposited) is automatic via the communal_reserve norm plugin.

### R7: Penalty for non-compliance (reduced quota)
- **Text**: A fisher who fails to deposit the required 10% will have their next quota reduced to 6% of lake weight until they catch up.
- **Classification**: graduated_sanction
- **Clarity**: CLEAR
- **Note**: The operationalization doesn't specify what "catch up" means - presumably it means making the missed deposit. The reduced quota applies to "next quota" which we interpret as the next trip/round.
- **Test**: After a violation (no 10% deposit), agent's next trip limit is 6% instead of 12%; normal 12% limit resumes after one compliant trip with reduced catch

## Implementation Summary

| Fragment | Shape | Parameters | Owner | Verification |
|----------|-------|------------|-------|--------------|
| 12% catch limit | catch_constraint | limit_pct_of_stock: 0.12 | norms/catch_limit.py (catch_limit) | tests/norms/test_catch_limit.py |
| 10% reserve deposit | financial_obligation | deposit_pct: 0.10, target: "communal_reserve" | norms/communal_reserve.py (communal_reserve) | tests/norms/test_communal_reserve.py |
| Excess to reserve | catch_constraint | (via existing reserve logic) | norms/reserve.py (reserve) | tests/norms/test_reserve.py |
| Lake replenishment trigger | replenishment_rule | threshold_kg: 100 | norms/communal_reserve.py (communal_reserve) | tests/norms/test_communal_reserve.py |
| Reduced quota penalty | graduated_sanction | trigger_sanction: "missed_deposit", reduced_pct: 0.06, normal_pct: 0.12 | norms/compliance_check.py (compliance_check) | tests/norms/test_compliance_check.py |

## Classification

This norm is **partially parametric, partially new plugin**:
- Uses existing `catch_limit` norm type for the 12% limit (parametric)
- Uses existing `reserve` norm type for excess allocation (parametric)
- Requires new `communal_reserve` norm type for:
  - 10% mandatory deposit from each catch
  - Lake replenishment when stock < 100kg
- Requires new `compliance_check` norm type for:
  - Tracking deposit compliance
  - Applying reduced quota (6%) for non-compliant fishers

## Config Changes Required

```json
{
  "norms": [
    {"type": "catch_limit", "id": "catch_limit", "limit_pct_of_stock": 0.12},
    {"type": "reserve", "id": "reserve", "shortfall_threshold_kg": 5, "max_withdrawal_kg": 0, "starting_balance_kg": 0},
    {"type": "communal_reserve", "id": "communal_reserve", "deposit_pct": 0.10, "replenish_threshold_kg": 100},
    {"type": "compliance_check", "id": "compliance_check", "trigger_sanction": "missed_deposit", "reduced_pct": 0.06, "normal_pct": 0.12}
  ]
}
```

## Notes

- Order matters in norm configuration:
  1. `catch_limit` - caps catch at 12% of stock, generates "over_cap" sanction if exceeded
  2. `reserve` - deposits excess (raw_kg - proposed_kg) from catch_limit
  3. `communal_reserve` - deducts 10% from final kept amount, handles lake replenishment at round end
  4. `compliance_check` - checks if 10% was deposited, applies reduced quota for next round if not

- The `communal_reserve` norm has dual responsibilities:
  - During `evaluate()`: deducts 10% deposit from each fisher's kept amount
  - During `on_round_end()`: if stock_kg < 100, adds reserve balance to stock and resets reserve

- The `compliance_check` norm:
  - Tracks which agents made their 10% deposit each round
  - Applies a reduced catch limit (6% instead of 12%) for agents who missed the previous deposit
  - Uses persistent state to remember non-compliant agents across rounds

- The existing `reserve` norm is repurposed here: set `max_withdrawal_kg: 0` to disable the withdrawal feature since the reserve is "used only for lake replenishment" (not for topping up short trips per the policy intent, though R5 acknowledges support for fishers below 5kg which we mark as incomplete).

```json
{
  "round": 3,
  "classification": [
    {"rule": "12% catch limit", "shape": "catch_constraint", "parametric": true, "owner": "norms/catch_limit.py", "verification": "tests/norms/test_catch_limit.py"},
    {"rule": "10% reserve deposit", "shape": "financial_obligation", "parametric": false, "owner": "norms/communal_reserve.py", "verification": "tests/norms/test_communal_reserve.py"},
    {"rule": "Lake replenishment when stock < 100kg", "shape": "replenishment_rule", "parametric": false, "owner": "norms/communal_reserve.py", "verification": "tests/norms/test_communal_reserve.py"},
    {"rule": "Reduced quota for non-compliance", "shape": "graduated_sanction", "parametric": false, "owner": "norms/compliance_check.py", "verification": "tests/norms/test_compliance_check.py"}
  ],
  "phases_added": [],
  "requires_new_plugin": true,
  "clarifications_needed": 2
}
```
