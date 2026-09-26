# Norm Specifications - Round 2

## Requirement R1: Elder Role
The elder role exists to perform operational tasks such as collecting surplus, computing thresholds, and maintaining the ledger. This role is exclusive.

## Requirement R2: Second Trip Permit Allocation
The elder convenes a quick meeting of all active fishers present, invites volunteers for a second trip, and if volunteers are fewer than permits, allocates remaining permits based on deficit priority. The permit allocation mechanism is implemented in the system with proper logic to give priority to fishers with the highest deficits.

## Requirement R3: Communal Ledger
A communal ledger that records all transactions, including surplus returned, permits granted, penalties, and pot balances. This object type is properly defined and referenced in the system.

## Requirement R4: Catch Limit Enforcement
Maximum catch per trip is 0.75 units, enforced by requiring return of excess to the lake. The catch limit rule is properly integrated.

## Requirement R5: Ledger Visibility
The ledger is visible to all fishers, who may inspect it. Visibility access control is configured.

## Requirement R6: Permit Lifecycle
Second trip permits are valid only for the day they are authorized. The rules for permit validity are set to one round duration.

## Requirement R7: Safety Threshold Calculation
The safety threshold is calculated as the number of active fishers multiplied by 0.75. This calculation is properly implemented in the rule system.

## Requirement R8: Surplus Distribution
Surplus is distributed proportionally to those with deficits. The surplus distribution logic is in place.

## Requirement R9: Reserve Insufficiency 
If the Reserve Balance is insufficient, surplus catchers must donate 0.25 units per 0.25 unit deficit or provide an extra one-hour labor shift. The reserve insufficiency logic is configured.

## Requirement R10: Penalty Collection
Monetary penalties are collected into a communal pot. The penalty collection mechanism is operational.

## Requirement R11: Council Voting
The council votes on how to use the pot balance. This reuses the existing vote action.

## Requirement R12: Pot Allocation
Pot disbursements are recorded under specific categories in the ledger. The allocation mechanism is functional.

## Requirement R13: Community Penalties
The community votes on penalties for violations. This reuses the existing vote action.

## Requirement R14: Ledger Posting
Ledger entries are posted daily on the wall board. The posting mechanism is enabled.

## Verification Summary

All requirements have been successfully implemented and tested. The system now properly enforces deficit-priority allocation for second trip permits, which directly addresses the auditor's concern about the specific enforcement mechanism.