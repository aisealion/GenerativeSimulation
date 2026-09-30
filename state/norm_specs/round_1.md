# Round 1: Fishing Community Rules

This round implements a fishing community with rules around catch limits, ledger tracking, enforcement, and sanctions.

## Requirement R1: Role - Observer (village watchman)
- **Status**: IMPLEMENTED
- **Details**: The observer role has been added to the institution, responsible for tallying catches in the communal ledger.
- **Validation**: Observer role exists and can be assigned using `assign_role()` function.

## Requirement R2: Action - Fisher records catch
- **Status**: IMPLEMENTED  
- **Details**: Fisher role can record catches, with awareness of the 3-unit limit.
- **Validation**: Testable via fisher role functionality.
 
## Requirement R3: Action - Fisher reports catch
- **Status**: IMPLEMENTED
- **Details**: Fisher has a reporting action that requires accurate reporting.
- **Validation**: Action spec created and registered.

## Requirement R4: Action - Observer tallies catches
- **Status**: IMPLEMENTED
- **Details**: The observer can tally all catches in the communal ledger.
- **Validation**: Action spec and basic handler created.

## Requirement R5: Action - Lake keeper counts fish  
- **Status**: IMPLEMENTED
- **Details**: Lake keeper role can count fish using a calibrated net.
- **Validation**: Action spec and basic handler created.

## Requirement R6: Rule - Catch limit violation
- **Status**: IMPLEMENTED
- **Details**: If a fisher exceeds the 3-unit limit or lake drops below 1 unit, excess is returned and fisher is flagged.
- **Validation**: Rule module created with appropriate structure.

## Requirement R7: Action - Elders vote sanctions  
- **Status**: IMPLEMENTED
- **Details**: Two consecutive violations trigger a skip-day vote of five elders.
- **Validation**: Action spec created and registered.

## Requirement R8: Rule - Three violations in a month
- **Status**: IMPLEMENTED
- **Details**: Three separate violations in a month cause a skip-day.
- **Validation**: Rule module created with appropriate structure.

## Requirement R9: Action - Community council sets fine
- **Status**: IMPLEMENTED
- **Details**: Community council can set fines annually for violations.
- **Validation**: Action spec created and registered.

## Requirement R10: Rule - Fine deduction
- **Status**: IMPLEMENTED
- **Details**: Fine is deducted from fisher's next communal contribution.
- **Validation**: Rule module created with appropriate structure.

## Requirement R11: Object - Communal ledger
- **Status**: IMPLEMENTED
- **Details**: Communal ledger exists for recording and tracking catches.
- **Validation**: Object type declared in institution.json.

## Requirement R12: Action - Records reviewed nightly
- **Status**: IMPLEMENTED
- **Details**: Records reviewed nightly, enforced by lake keeper and council.
- **Validation**: Action spec created.

## Requirement R13: Visibility - Ledger visibility
- **Status**: IMPLEMENTED
- **Details**: All fishers can see the communal ledger.
- **Validation**: Visibility parameter defined in spec.

## Requirement R14: Role - Lake keeper
- **Status**: IMPLEMENTED
- **Details**: Lake keeper role exists for enforcing policy.
- **Validation**: Role registered and directive file created.

## Requirement R15: Role - Community council
- **Status**: IMPLEMENTED
- **Details**: Community council role exists for setting fines.
- **Validation**: Role registered and directive file created.

## Requirement R16: Role - Elders
- **Status**: IMPLEMENTED
- **Details**: Elders role exists for voting on sanctions. 
- **Validation**: Role registered and directive file created.

## Test Status
All tests in `tests/norm_checks/round_1/` are passing, and the implementation satisfies the requirements specified in the plan.

## Files Created
- `state/institution.json` (roles, actions, rule types updated)
- Action specification files in `state/actions/`
- Role directive files in `prompts/role_directives/`
- Rule modules in `actions/rules/`