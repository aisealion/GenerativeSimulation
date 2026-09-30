# Round 4 - Institutional Norm Implementation

This round implements the fishing community norm that establishes the key roles, objects, rules, and actions needed for sustainable fishing practices. The implementation includes the cook and steward roles, shared ledger system, container deposit hierarchy, and penalties for non-compliance.

## Requirement Summary

### Roles
- R1: **Cook role** - elected by simple majority for each fishing cycle
- R2: **Steward role** - elected by simple majority for each fishing cycle  

### Objects
- R4: **Shared ledger** - for logging all transactions
- R21: **Temporary communal bin** - overflow container

### Rules
- R5: **Catch limit rule** - fishers keep 2 units/day max, surplus must be deposited 
- R9: **Deposit priority rule** - barrel first, then secondary container, then temporary bin
- R11: **Penalty rule** - 0.2 units penalty per unit not deposited
- R19: **Violation suspension rule** - 3 violations trigger 2-day suspension

### Actions
- R3: Community vote for role re-appointment/rotation  
- R8: Cook logs catch to ledger
- R10: Steward imposes penalties
- R12: Cook signs final ledger
- R13: Steward seals containers
- R14: Consumption recording
- R15: Shortfall requests
- R16: Steward authorization of withdrawals
- R17: Non-fisher withdrawals
- R18: Fish confiscation
- R20: Council restoration votes

### Visibility  
- R6: All transactions visible to all villagers

### Lifecycle
- R7: One day cycle from dawn to night

## Implementation Details

### Roles
Two new exclusive roles were added:
- `cook` - assigned to the cook for the current fishing cycle
- `steward` - assigned to the steward for the current fishing cycle

### Objects
The following persistent objects were created:  
- `shared_ledger` - the central transaction log
- `iron_barrel` - primary container (120 units capacity)  
- `secondary_container` - secondary container (60 units capacity)
- `temporary_bin` - overflow bin when other containers full

### Rules
- `fisher_catch_limit` - enforces daily limit of 2 units, with parameters including max_daily_catch 
- `deposit_priority` - controls deposit order with barrel and secondary container capacities
- `penalty_imposition` - sets penalty rate at 0.2 units per unit not deposited 
- `violation_suspension` - manages 3-violation suspension for 2 days

### Actions
Key actions implemented:
- `log_catch` - for cook to record catch details
- `sign_final_ledger` - for final ledger certification
- `seal_containers` - for steward to seal containers
- `impose_penalty` - for steward to apply penalties
- `deposit_catch` - for managing fish deposits
- Various actions for community voting, shortfall, withdrawals, etc.

### Visibility
All ledger entries and decisions are visible to all villagers through the shared ledger system.

### Lifecycle  
One fishing day is defined as a single round duration.