# Round 2 Institution Specification

## Requirement R1
**Type:** ROLE
**Description:** Steward role responsible for sealing the iron barrel reserve.

The steward role is responsible for managing the communal fish reserve. This role is registered with the institution and has specific duties in the fishery management system.

## Requirement R2
**Type:** ACTION
**Description:** Fisher logs total catch on shared ledger after each fishing trip.

Fisher agents must log their total catch on the shared ledger after each fishing trip. This action requires judgment from the fisher about the amount to log.

## Requirement R3
**Type:** OBJECT
**Description:** Iron barrel reserve for surplus fish, sealed by steward.

The iron barrel reserve is a persistent object designed to store surplus fish. It is managed by the steward and is sealed to prevent unauthorized access.

## Requirement R4
**Type:** RULE
**Description:** Maximum of 2 units of fish retained per day.

Fishers are limited to retaining a maximum of 2 units of fish per day. This rule prevents excessive personal retention and ensures fair distribution.

## Requirement R5
**Type:** ACTION
**Description:** Fisher deposits surplus into iron barrel reserve.

Fisher agents may choose whether to deposit surplus fish into the iron barrel reserve after each fishing trip.

## Requirement R6
**Type:** ACTION
**Description:** Steward seals the iron barrel reserve until end of day.

The steward is responsible for sealing the iron barrel reserve at the end of each day, preventing further access to the reserve.

## Requirement R7
**Type:** ACTION
**Description:** Cook signs and records deposit immediately.

The cook has the responsibility to sign and record each deposit transaction immediately upon submission.

## Requirement R8
**Type:** ACTION
**Description:** Fisher records daily fish consumption on ledger.

Fisher agents must record their daily fish consumption on the ledger, with each entry requiring judgment from the fisher about the amount.

## Requirement R9
**Type:** ACTION
**Description:** Cook signs to certify fish consumption amount.

The cook signs to certify fish consumption amounts, ensuring the accuracy of consumption records.

## Requirement R10
**Type:** ACTION
**Description:** Fisher submits shortfall request if consumption below 1 unit.

Fisher agents may submit a shortfall request if their consumption falls below 1 unit in a day.

## Requirement R11
**Type:** ACTION
**Description:** Steward authorizes withdrawal up to shortfall amount.

The steward authorizes withdrawal requests up to the shortfall amount, ensuring that fishers can access necessary resources.

## Requirement R12
**Type:** ACTION
**Description:** Steward debits reserve balance and logs transaction.

The steward debits the reserve balance and logs each transaction to maintain accurate accounting.

## Requirement R13
**Type:** ACTION
**Description:** Non-fisher villager submits withdrawal request up to 1 unit daily.

Non-fisher villagers may submit withdrawal requests up to 1 unit of fish per day, with proper authorization.

## Requirement R14
**Type:** VISIBILITY
**Description:** All villagers can view reserve status on shared ledger.

All villagers have visibility into the reserve status on the shared ledger, enabling transparent monitoring of fish reserves.

## Requirement R15
**Type:** ACTION
**Description:** Steward confiscates missing fish deposits and imposes penalty.

The steward confiscates fish deposits that were not properly submitted and imposes penalties according to the established rule system.

## Requirement R16
**Type:** RULE
**Description:** Penalty of 0.2 units per un-deposited unit.

For each unit of fish that is not properly deposited, a penalty of 0.2 units is imposed on the fisher.

## Requirement R17
**Type:** ACTION
**Description:** Violation counter increments for each missing deposit.

The system automatically increments a violation counter for each missing fish deposit.

## Requirement R18
**Type:** ACTION
**Description:** Fishers vote on suspension after three violations.

When a fisher accumulates three violations, fishers vote on whether to suspend their fishing rights.

## Requirement R19
**Type:** RULE
**Description:** Suspension of fishing rights for 2 days or until penalties paid.

When a fisher's rights are suspended, they are suspended for 2 days or until their penalties are paid, whichever is longer.

## Requirement R20
**Type:** ACTION
**Description:** Steward opens reserve only for authorized transactions and updates ledger.

The steward opens the reserve only for authorized transactions and updates the ledger accordingly.

## Requirement R21
**Type:** OBJECT
**Description:** Shared ledger for recording all transactions and consumption.

The shared ledger is a persistent object that records all transactions and consumption across the fishery.

```json
{
  "requirement_evidence": [
    "R1: Created steward role in state/institution.json",
    "R2: Created log_catch action specification in state/actions/log_catch.json",
    "R3: Created iron_barrel_reserve object type in state/object_types/iron_barrel_reserve.json",
    "R4: Created fish_retention_rule in state/institution.json",
    "R5: Created deposit_surplus action specification in state/actions/deposit_surplus.json",
    "R6: Created seal_barrel action specification in state/actions/seal_barrel.json",
    "R7: Created sign_deposit action specification in state/actions/sign_deposit.json",
    "R8: Created record_consumption action specification in state/actions/record_consumption.json",
    "R9: Created certify_consumption action specification in state/actions/certify_consumption.json",
    "R10: Created submit_shortfall action specification in state/actions/submit_shortfall.json",
    "R11: Created authorize_withdrawal action specification in state/actions/authorize_withdrawal.json",
    "R12: Created debit_reserve action specification in state/actions/debit_reserve.json",
    "R13: Created submit_withdrawal action specification in state/actions/submit_withdrawal.json",
    "R14: Created visibility rule in state/institution.json",
    "R15: Created confiscate_deposit action specification in state/actions/confiscate_deposit.json",
    "R16: Created penalty_rule in state/institution.json",
    "R17: Created violation_counter in state/institution.json",
    "R18: Created vote_suspension action specification in state/actions/vote_suspension.json",
    "R19: Created suspension_rule in state/institution.json",
    "R20: Created open_reserve action specification in state/actions/open_reserve.json",
    "R21: Created shared_ledger object type in state/object_types/shared_ledger.json"
  ],
  "verification_failures": []
}
```