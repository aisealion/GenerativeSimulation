# Round 4 Norm Specifications

This file documents the norm specifications implemented for Round 4 of the fishery simulation.

## Requirement R1: Cook Role
The cook role exists, elected by a simple majority of fishers at the start of each fishing cycle.
- agent_experience: knows they are designated as cook for the current fishing cycle

## Requirement R2: Steward Role  
The steward role exists, elected by a simple majority of fishers at the start of each fishing cycle.
- agent_experience: knows they are designated as steward for the current fishing cycle

## Requirement R3: Community Vote Decision
Fisher decides whether to re-appoint or rotate the cook and steward by community vote.
- agent_experience: knows current cook and steward roles exist; decides whether to re-appoint or rotate the cook and steward

## Requirement R4: Shared Ledger
Shared ledger for logging catches, deposits, withdrawals, penalties, and other transactions.
- agent_experience: observes All transactions and decisions are visible on the shared ledger

## Requirement R5: Fisher Catch Limit
The fisher keeps up to 2 units of fish per day; surplus must be deposited.
- agent_experience: may_do Keep up to 2 units of fish per day; may_not_do Keep more than 2 units of fish per day without depositing surplus

## Requirement R6: Ledger Visibility
All deposits, withdrawals, consumptions, violations, penalties, suspensions, and restoration decisions are visible to all villagers.
- agent_experience: observes All transactions and decisions are visible on the shared ledger

## Requirement R7: Fishing Cycle Duration
One whole day of fishing, from dawn to night when the cook signs the final ledger entry.
- agent_experience: observes The entire day's cycle from start to final entry signing

## Requirement R8: Cook Logs Catch
Fisher logs the total catch on the shared ledger with timestamp.
- agent_experience: knows They must log their catch on the shared ledger; decides The exact timestamp and amount of catch to log

## Requirement R9: Deposit Order
Surplus is deposited into the iron barrel first, then secondary container, then temporary bin if both are full.
- agent_experience: may_do Deposit surplus into the appropriate container based on availability

## Requirement R10: Steward Imposes Penalty
Steward logs each transfer and imposes a penalty of 0.2 units per unit of fish not deposited.
- agent_experience: knows They must log transfers and impose penalties for non-deposited fish; decides The exact penalty amount based on non-deposited fish

## Requirement R11: Penalty Rule
Penalty of 0.2 units per unit of fish not deposited into the barrel or secondary container.
- agent_experience: may_not_do Fail to deposit surplus fish without incurring a penalty

## Requirement R12: Cook Signs Final Ledger
Cook signs the final ledger entry at the end of the day.
- agent_experience: knows They must sign the final ledger entry at the end of the day

## Requirement R13: Steward Seals Containers
Steward seals the iron barrel and secondary container (and temporary bin if used).
- agent_experience: knows They must seal the containers at the end of the day

## Requirement R14: Consumption Recording
Fisher records daily consumption on the ledger; cook signs to certify.
- agent_experience: knows They must record consumption and have it certified

## Requirement R15: Shortfall Request
Fisher submits a shortfall request on the ledger if consumption falls below 1 unit.
- agent_experience: knows They must submit a shortfall request if consumption is below 1 unit

## Requirement R16: Withdrawal Authorization  
Steward authorizes a withdrawal from the communal reserve up to the shortfall.
- agent_experience: knows They must authorize withdrawals for shortfalls

## Requirement R17: Non-Fisher Withdrawal
Non-fisher villagers may withdraw up to 1 unit per day if reserves are available.
- agent_experience: knows Non-fisher villagers may withdraw up to 1 unit per day

## Requirement R18: Fish Confiscation
Steward confiscates missing fish, deposits into reserve, records penalty, increments violation counter.
- agent_experience: knows They must confiscate and record missing fish

## Requirement R19: Violation Suspension
Three violations result in suspension of fishing rights for two days or until penalties are paid and compliance is demonstrated.
- agent_experience: may_not_do Accumulate three violations without facing suspension

## Requirement R20: Council Restoration Vote
Council votes to restore fishing rights after suspension.
- agent_experience: knows They must vote to restore fishing rights after suspension

## Requirement R21: Temporary Bin Object
Temporary communal bin on the lakebank for overflow when both barrel and secondary container are full.
- agent_experience: observes Temporary bin is available for overflow

## Verification Results

- All structural/compilation errors have been resolved
- All tests pass
- Implementation follows the established patterns from existing action handlers
- The system is now ready for testing and audit