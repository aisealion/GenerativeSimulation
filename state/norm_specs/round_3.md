# Round 3 Norm Specification

## Requirement R1
**Type**: ACTION
**Name**: observer_check_stock
**Description**: Observer checks lake stock before trip

## Requirement R2
**Type**: ACTION
**Name**: observer_flag_violation  
**Description**: Observer flags fisher for violations

## Requirement R3
**Type**: ACTION
**Name**: observer_impose_skip_day
**Description**: Observer imposes skip day penalties

## Requirement R4
**Type**: ACTION
**Name**: observer_update_ledger
**Description**: Observer updates communal ledger with catch reports

## Requirement R5
**Type**: ACTION
**Name**: fisher_report_catch
**Description**: Fisher reports catch and contribution to observer before sunset

## Requirement R6
**Type**: ACTION
**Name**: lake_keeper_execute_withdrawal
**Description**: Lake keeper executes withdrawal from communal ledger

## Requirement R7
**Type**: ACTION
**Name**: lake_keeper_update
**Description**: Lake keeper updates lake stock levels

## Requirement R8
**Type**: ACTION
**Name**: community_council_set_fine
**Description**: Community council sets fines for violations

## Requirement R9
**Type**: RULE
**Name**: MaxCatchLimit
**Description**: Maximum catch per trip is three units

## Requirement R10
**Type**: RULE
**Name**: StockLimit
**Description**: Trip denied if lake stock < 1 unit; excess fish returned

## Requirement R11
**Type**: RULE
**Name**: ViolationTracker
**Description**: Tracks violations and enforces skip days and fines

## Requirement R12
**Type**: VISIBILITY
**Name**: CommunityLedgerVisibility
**Description**: All community members can read communal ledger

## Requirement R13
**Type**: VISIBILITY
**Name**: PersonalLedgerVisibility  
**Description**: Fisher can read personal ledger

## Requirement R14
**Type**: OBJECT
**Name**: CommunalLedger
**Description**: Communal ledger records all transactions

## Requirement R15
**Type**: OBJECT
**Name**: PersonalLedger
**Description**: Personal ledger records individual fisher transactions

## Requirement R16
**Type**: ROLE
**Name**: Observer
**Description**: Observer role for monitoring fishery activities