# Round 1 - Norm Specification

## R1: Each fisher records total catch on the shared ledger and signs it.
- **Action**: `record_catch` (new)
- **Agent Experience**: Fishers record their catch and sign the ledger
- **Notes**: This action has not been fully implemented yet

## R2: Designated pool distributor (selected by rotating alphabetical order of last names)
- **Role**: `pool distributor` 
- **Agent Experience**: Fishers must know who the current distributor is and how they were chosen
- **Notes**: This role has not been fully implemented yet

## R3: Distributor checks the ledger for entries over 2 units
- **Action**: `check_ledger` (existing) 
- **Agent Experience**: Distributor must monitor catch limits
- **Notes**: This action has not been fully implemented yet

## R4: Excess units are added to the pool, with a 0.5-unit fine per excess unit
- **Rule**: `fine_enforcement` applied to `check_ledger`
- **Description**: Applies 0.5 unit fine per excess unit beyond 2-unit limit
- **Params**: `fine_per_unit=0.5`, `limit=2.0`
- **Agent Experience**: 
  - Fishers must know that excess units are penalized
  - Fishers may not exceed catch limit without penalty
  - After recording, if over the limit, fine applied

## R5: Distributor collects pool contributions and calculates total pool
- **Action**: `collect_pool` (existing)
- **Agent Experience**: Distributor manages communal pool
- **Notes**: This action has not been fully implemented yet

## R6: Distributor identifies fishers with personal consumption <1 unit and calculates shortfalls
- **Action**: `identify_shortfalls` (existing)
- **Agent Experience**: Distributor identifies needy fishers
- **Notes**: This action has not been fully implemented yet

## R7: Distributor redistributes the pool equally among shortfallers
- **Action**: `redistribute_pool` (existing)
- **Agent Experience**: Distributor ensures fair redistribution 
- **Notes**: This action has not been fully implemented yet

## R8: Fisher, distributor, and second fisher sign the ledger entry
- **Action**: `sign_ledger_entry` (existing)
- **Agent Experience**: Three parties must verify ledger entries
- **Notes**: This action has not been fully implemented yet

## R9: Unpaid fine results in personal consumption forfeiture
- **Rule**: `fine_consequence` (placeholder) 
- **Description**: Unpaid fines lead to loss of consumption rights
- **Notes**: Implementation pending

## R10: Shared ledger for catch recording (reuses the existing shared ledger object)
- **Object**: Shared ledger object reused
- **Notes**: This object reuse is functional