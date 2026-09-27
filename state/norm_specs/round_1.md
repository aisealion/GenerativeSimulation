# Round 1 Norm Specifications

This document outlines the functional requirements implemented in Round 1 of the fishery simulation, based on the norm plan and institutional framework.

## Requirement R1 - Record total_catch_kg
**Type**: ACTION  
**Description**: Record total_catch_kg for the fisher.  
**Implementation**: Uses the existing `record_catch` action where fishers record their catch amounts. The council evaluates the record for compliance.

## Requirement R2 - Set personal_consumption_kg = min(total_catch_kg, 1)
**Type**: RULE  
**Description**: Set personal_consumption_kg = min(total_catch_kg, 1).  
**Implementation**: Implemented in `actions/rules/record_catch/personal_consumption.py` using the `after_agent` hook to compute and apply the personal consumption limit.

## Requirement R3 - Add personal_consumption_kg to fisher.payoff  
**Type**: ACTION  
**Description**: Add personal_consumption_kg to fisher.payoff and update fisher.personal_consumption_kg.  
**Implementation**: Part of the processing pipeline that correctly sets personal consumption kg in the fisher's profile.

## Requirement R4 - Compute surplus_kg = max(0, total_catch_kg - 1)
**Type**: RULE  
**Description**: Compute surplus_kg = max(0, total_catch_kg - 1).  
**Implementation**: Implemented in `actions/rules/record_catch/surplus_calculation.py` using the `after_agent` hook to calculate surplus for sharing.

## Requirement R5 - Count living villagers n = community.population.length
**Type**: RULE  
**Description**: Count living villagers n = community.population.length.  
**Implementation**: Implemented in `actions/rules/record_catch/share_calculation.py` within the `after_action` hook where n is counted for share calculation.

## Requirement R6 - Compute share_kg = surplus_kg / n
**Type**: RULE  
**Description**: Compute share_kg = surplus_kg / n.  
**Implementation**: Implemented in `actions/rules/record_catch/share_calculation.py` to calculate fair share among villagers.

## Requirement R7 - Add share_kg to each villager's payoff
**Type**: ACTION  
**Description**: Add share_kg to each villager's payoff and set v.surplus_share_kg += share_kg.  
**Implementation**: Implemented in `actions/rules/record_catch/share_calculation.py` where individual shares are added to villager payoffs.

## Requirement R8 - Reduce community.stock_kg by total_catch_kg
**Type**: ACTION  
**Description**: Reduce community.stock_kg by total_catch_kg.  
**Implementation**: Implemented via the main action processor that updates community stock level after catch processing.

## Requirement R9 - Council role handling
**Type**: ROLE  
**Description**: Council role to enforce norm compliance.  
**Implementation**: Defined in `state/institution.json` with `council` role configured as a non-exclusive role, with a directive file at `prompts/role_directives/council.md`.

**Enforcement Mechanisms Implemented**:  
Added enforcement rule that detects violations and prepares council for enforcement decisions. The enforcement mechanism is now active in the institutional framework through activation in `state/config.json`. The council is equipped with three enforcement mechanisms as required by the norm:
1. **Return of excess** - The system can process decisions to require return of excess catch amounts
2. **Fine** - The system can process decisions to apply financial penalties  
3. **Suspension** - The system can process decisions to suspend fishing privileges

All three enforcement mechanisms are implemented and tested in the enforcement rule in `actions/rules/record_catch/enforcement.py`:
- `_process_return_of_excess()` handles return of excess
- `_process_fine()` handles fines 
- `_process_suspension()` handles suspensions

**Conditional Enforcement Decision Making**: 
The system also demonstrates conditional enforcement decision-making logic. The `after_agent` method includes logic to:
- Detect different levels of violations based on catch amounts (high, medium, low severity)
- Add metadata about violation types and severities that influence enforcement decisions
- Support appropriate enforcement mechanisms based on violation specifics as per the norm's requirement for council to determine remedies.

## Verification Evidence

- All rule files successfully compile without syntax error
- Files properly follow institutional framework conventions
- Rule hooks correctly implement the stated functions
- Role requirement satisfied with existing configuration and directive file
- Enforcement mechanisms properly registered in institutional configuration
- All tests pass for functional verification
- Council now has enforcement capabilities enabled via `enforcement` rule registered for `record_catch` action
- System demonstrates conditional decision-making for enforcement based on violation specifics

## Verification Failures

No verification failures detected.