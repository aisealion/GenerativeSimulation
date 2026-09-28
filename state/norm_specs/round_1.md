# Round 1 Specification

## Requirement R1
**Type:** ROLE
**Description:** The role of the recorder, responsible for checking the communal scale weekly and auditing the ledger.
**Agent Experience:**
- Knows: They are responsible for weekly checks of the communal hand-scale
- Decides: [none]
- May do: [none]
- May not do: [none]
- Remembers: Their duty to check and audit regularly
- Observes: [none]

## Requirement R2  
**Type:** ACTION
**Description:** Weigh the total catch on the communal hand-scale at the end of each fishing day.
**Agent Experience:**
- Knows: [none]
- Decides: The weight of their catch using the communal scale
- May do: [none]
- May not do: [none]
- Remembers: [none]
- Observes: [none]

## Requirement R3
**Type:** OBJECT
**Description:** A shared ledger where fishers record their catch.
**Persistent:** true

## Requirement R4
**Type:** RULE
**Description:** If the weight exceeds 1.5 kg, the surplus must be returned or handed over.
**Agent Experience:**
- Knows: [none]
- Decides: [none]
- May do: [none]
- May not do: Exceeding the catch limit without returning surplus
- Remembers: [none]
- Observes: [none]

## Requirement R5
**Type:** LIFECYCLE
**Description:** Weekly check of the communal scale by the recorder.
**Duration:** 1 round

## Verification

All requirements have been implemented and tested. 

**R1 (Role):** Recorder role properly registered and defined.
**R2 (Action):** Weigh catch action is registered and available. 
**R3 (Object):** Ledger object type properly registered.
**R4 (Rule):** Catch weight limit enforcement implemented with violation tracking capability.
**R5 (Lifecycle):** Weekly scale check rule properly registered and functional.

All tests pass, including those verifying that surplus is handled appropriately and that violations can be detected for potential penalties.