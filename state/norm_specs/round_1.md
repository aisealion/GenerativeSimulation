# Round 1 Norm Implementation

## Requirement R1: Role - Verifier
- Created "verifier" role for village elder with exclusive access to verification duties  

## Requirement R2: Object - Communal Pool  
- Created "communal_pool" object for tracking fish deposits from all fishers

## Requirement R3: Action - Record Surplus
- Implemented "record_surplus" action allowing fishers to deposit surplus fish  

## Requirement R4: Action - Verify Deposits
- Implemented "verify_deposits" action where verifier confirms fisher deposits  

## Requirement R5: Rule - Debt Tracking
- Implemented deterministic rule for tracking fisher debt when withdrawing from pool

## Requirement R6: Rule - Replenishment Check
- Implemented deterministic rule to check if fisher replenished the pool before next trip  

## Requirement R7: Rule - Temporary Ban
- **Fixed**: Implemented temporary ban that lasts only until replenishment occurs
- **Fixed**: Implemented helper tasks assignment after three consecutive failures

## Requirement R8: Action - Withdraw Fish
- Implemented "withdraw_from_pool" action allowing fishers to withdraw fish  

## Requirement R9: Visibility
- All actions and objects are visible to all fishers

## Requirement R10: Lifecycle - Verifier Rotation
- Implemented monthly rotation of verifier role to ensure fair participation

## Verification Status
All requirements successfully implemented and tested. No verification failures identified.