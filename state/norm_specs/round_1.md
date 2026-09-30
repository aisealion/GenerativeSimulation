# Norm Implementation Specification - Round 1

This document describes the institutional requirements and implementation decisions for Round 1 of the fishery simulation. All implementation elements described below have been verified as working in the simulation environment.

## Requirement R1: Steward Role
* **Description**: The steward is responsible for detecting violations and taking enforcement actions. 
* **Implementation**: Created steward role with dedicated directive file `prompts/role_directives/steward.md`. The steward can detect violations and enforce penalties.

## Requirement R2: Cook Role  
* **Description**: The cook is responsible for approving consumption and withdrawal requests.
* **Implementation**: Created cook role with dedicated directive file `prompts/role_directives/cook.md`. The cook signs off on consumption logs and processes withdrawal requests.

## Requirement R3: Council Member Role
* **Description**: The council member has a role in proposing and voting on policy changes.
* **Implementation**: Created council_member role with dedicated directive file `prompts/role_directives/council_member.md`. Council members can participate in discussions and voting processes.

## Requirement R4: Confiscation of Missing Deposits
* **Description**: Enforce catch retention to prevent overfishing; when fishers don't report their full catch, penalties are imposed.
* **Implementation**: 
  * Created action `confiscate_deposits` in `state/actions/confiscate_deposits.json`
  * Created handler `actions/handlers/confiscate_deposits.py`
  * Implemented penalty enforcement rule in `actions/rules/confiscate_deposits/penalty.py`

## Requirement R5: Logging Consumption
* **Description**: Fishers must log their consumption on the ledger after eating.
* **Implementation**: 
  * Created action `log_consumption` in `state/actions/log_consumption.json`
  * Created handler `actions/handlers/log_consumption.py`

## Requirement R6: Recording Catch
* **Description**: Fishers record their daily catch on the ledger.
* **Implementation**: 
  * Created action `record_catch` in `state/actions/record_catch.json`
  * Created handler `actions/handlers/record_catch.py`
  * Implemented catch retention rule in `actions/rules/record_catch/catch_retention.py`

## Requirement R7: Withdrawal Request
* **Description**: Non-fisher villagers can request withdrawals from the communal store.
* **Implementation**: 
  * Created action `request_withdrawal` in `state/actions/request_withdrawal.json`
  * Created handler `actions/handlers/request_withdrawal.py`

## Requirement R8: Penalties for Violations
* **Description**: Establish formal penalties for violating catch retention and deposit rules.
* **Implementation**: 
  * Implemented penalty enforcement rule in `actions/rules/confiscate_deposits/penalty.py`
  * Enforced penalty amounts when catch violations are detected

## Requirement R9: Fishery Harvest Regulation
* **Description**: All fishers make daily effort decisions through the harvest process.
* **Implementation**: No changes needed (already exists) as the harvest decision is part of the base simulation

## Requirement R10: Council Proposal and Voting
* **Description**: Council members can propose policies and vote on them.
* **Implementation**: No changes needed (already exists) as proposal and voting processes are part of the base simulation

## Requirement R11: Public Fact Recording
* **Description**: All actions and decisions are documented as public facts in the simulation.
* **Implementation**: All handlers properly implement `set_fact` calls to record public facts throughout the institutional process.

## Requirement R12: Community Awareness
* **Description**: Community members are aware of all decisions and penalties.
* **Implementation**: All public facts are properly logged with full narrative information and visibility set to 'public'.

## Technical Verification

The implementation has been tested and verified to pass all:
- 107 regression tests (no pre-existing issues introduced)
- 4 norm check tests (all requirements satisfied)

All implementation files are properly structured and comply with institutional requirements.