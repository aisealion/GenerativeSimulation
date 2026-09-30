# Round 3: Community Resource Management Norm

This round implements a norm for community resource management including fishing practices, storage systems, and stewardship protocols.

## Requirement R1: Cook and Steward Roles  
- **Role**: Adds new roles "cook" and "steward" to the fishing community
- **Description**: The cook role oversees fish preparation and consumption verification, while the steward manages communal resources and enforces community rules for resource access.

## Requirement R2: Shared Ledger Object 
- **Object**: `shared_ledger` (ledger type)
- **Description**: A shared ledger for recording catches, deposits, withdrawals, consumptions, violations, penalties, suspensions, and restorations
- **Visibility**: Public to all villagers

## Requirement R3: Fisher Deposit Decision 
- **Action**: `deposit_catch`
- **Description**: Fishers decide where to deposit surplus catch, either in the iron barrel or secondary container, based on current capacity.
- **Participants**: All alive fishers

## Requirement R4: Steward Container Sealing 
- **Action**: `seal_containers` 
- **Description**: The steward seals the iron barrel and secondary container until the end of the day.
- **Participants**: Steward

## Requirement R5: Cook Consumption Verification 
- **Action**: `verify_consumption`
- **Description**: The cook verifies and signs off on fisher's consumption of communal resources.
- **Participants**: Cook

## Requirement R6: Steward Withdrawal Authorization  
- **Action**: `authorize_withdrawal`
- **Description**: The steward authorizes withdrawals from the reserve based on shortfall requests.
- **Participants**: Steward

## Requirement R7: Non-Fisher Withdrawal Authorization
- **Action**: `authorize_non_fisher_withdrawal`
- **Description**: The steward authorizes withdrawals from the reserve for non-fisher villagers.
- **Participants**: Steward

## Requirement R8: Violation and Penalty Enforcement 
- **Rule**: `confiscate_and_penalty`
- **Description**: If a fisher fails to deposit surplus fish, the steward confiscates the missing portion, imposes a penalty of 0.2 units per un-deposited unit, and increments the violation counter.
- **Activation**: Active for deposit_catch action

## Requirement R9: Penalty to Reserve
- **Rule**: `penalty_to_reserve` 
- **Description**: The penalty amount is added to the communal reserve and recorded on the ledger.
- **Activation**: Active for deposit_catch action

## Requirement R10: Council Suspension Voting
- **Action**: `vote_suspension`
- **Description**: The council of fishers votes on suspension of fishers after three violations.
- **Participants**: Council of fishers

## Requirement R11: Council Restoration Voting  
- **Action**: `vote_restoration`
- **Description**: The council votes to restore suspended fisher's rights.
- **Participants**: Council of fishers

## Requirement R12: Ledger Visibility 
- **Visibility**: All ledger entries are visible to all villagers

## Requirement R13: Iron Barrel Object
- **Object**: `iron_barrel` (iron_barrel type)  
- **Description**: The primary communal reserve on the lakebank
- **Participants**: Fishers and stewards

## Requirement R14: Secondary Container Object
- **Object**: `secondary_container` (secondary_container type)
- **Description**: A secondary communal container on the lakebank used when the iron barrel is full
- **Participants**: Fishers and stewards

```json
{
  "requirement_evidence": [
    "R1: Cook and steward roles created in state/institution.json",
    "R2: Shared ledger object type and instance created in state/institution.json and state/objects.json",
    "R3: Deposit catch action defined in state/actions/deposit_catch.json",
    "R4: Seal containers action defined in state/actions/seal_containers.json",
    "R5: Verify consumption action defined in state/actions/verify_consumption.json",
    "R6: Authorize withdrawal action defined in state/actions/authorize_withdrawal.json",
    "R7: Authorize non-fisher withdrawal action defined in state/actions/authorize_non_fisher_withdrawal.json",
    "R8: Confiscate and penalty rule implemented in actions/rules/deposit_catch/confiscate_and_penalty.py",
    "R9: Penalty to reserve rule implemented in actions/rules/deposit_catch/penalty_to_reserve.py",
    "R10: Vote suspension action defined in state/actions/vote_suspension.json",
    "R11: Vote restoration action defined in state/actions/vote_restoration.json",
    "R12: Ledger visibility set to public in state/object_types/ledger.json",
    "R13: Iron barrel object type and instance created in state/institution.json and state/objects.json",
    "R14: Secondary container object type and instance created in state/institution.json and state/objects.json"
  ],
  "verification_failures": []
}
```