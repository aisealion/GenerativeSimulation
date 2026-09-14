Requirement: Fisher logs catch into communal ledger before setting out.
Purpose: Record each fisher's catch in the communal ledger.
Actor: fisher
Level (1/2/3/4): NOT_IMPLEMENTED_THIS_ROUND
Action this attaches to (which action's own decision or output does this concern): 
Action/Decision: 
Existing owner or new (a rule type under that action's own actions/rules/{action_name}/, an object type, or an action): NOT_IMPLEMENTED_THIS_ROUND
Inputs: 
Outputs: 
State read: 
State changed: 
Timing / Frequency: 
Participation: 
Gate: 
Institutional consequence: 
Agent-visible information: 
Verification: NOT_IMPLEMENTED_THIS_ROUND

Requirement: Treasurer totals daily catch at dusk.
Purpose: Compute total catch for the day.
Actor: treasurer
Level (1/2/3/4): NOT_IMPLEMENTED_THIS_ROUND
Action this attaches to (which action's own decision or output does this concern): 
Action/Decision: 
Existing owner or new (a rule type under that action's own actions/rules/{action_name}/, an object type, or an action): NOT_IMPLEMENTED_THIS_ROUND
Inputs: 
Outputs: 
State read: 
State changed: 
Timing / Frequency: 
Participation: 
Gate: 
Institutional consequence: 
Agent-visible information: 
Verification: NOT_IMPLEMENTED_THIS_ROUND

Requirement: Treasurer presents total and 20% threshold to council.
Purpose: Inform council of catch and cap.
Actor: treasurer
Level (1/2/3/4): NOT_IMPLEMENTED_THIS_ROUND
Action this attaches to (which action's own decision or output does this concern): 
Action/Decision: 
Existing owner or new (a rule type under that action's own actions/rules/{action_name}/, an object type, or an action): NOT_IMPLEMENTED_THIS_ROUND
Inputs: 
Outputs: 
State read: 
State changed: 
Timing / Frequency: 
Participation: 
Gate: 
Institutional consequence: 
Agent-visible information: 
Verification: NOT_IMPLEMENTED_THIS_ROUND

Requirement: Council votes on excess allocation.
Purpose: Decide how to allocate excess catch.
Actor: council (all fishers voting)
Level (1/2/3/4): NOT_IMPLEMENTED_THIS_ROUND
Action this attaches to (which action's own decision or output does this concern): 
Action/Decision: 
Existing owner or new (a rule type under that action's own actions/rules/{action_name}/, an object type, or an action): NOT_IMPLEMENTED_THIS_ROUND
Inputs: 
Outputs: 
State read: 
State changed: 
Timing / Frequency: 
Participation: 
Gate: 
Institutional consequence: 
Agent-visible information: 
Verification: NOT_IMPLEMENTED_THIS_ROUND

Requirement: Treasurer records decision and updates pot balance.
Purpose: Update communal ledger with pot changes.
Actor: treasurer
Level (1/2/3/4): NOT_IMPLEMENTED_THIS_ROUND
Action this attaches to (which action's own decision or output does this concern): 
Action/Decision: 
Existing owner or new (a rule type under that action's own actions/rules/{action_name}/, an object type, or an action): NOT_IMPLEMENTED_THIS_ROUND
Inputs: 
Outputs: 
State read: 
State changed: 
Timing / Frequency: 
Participation: 
Gate: 
Institutional consequence: 
Agent-visible information: 
Verification: NOT_IMPLEMENTED_THIS_ROUND

Requirement: Enforce per-trip catch cap of 15 kg.
Purpose: Limit fisher's trip catch.
Actor: fisher
Level (1/2/3/4): 3
Action this attaches to (which action's own decision or output does this concern): 
Action/Decision: 
Existing owner or new (a rule type under that action's own actions/rules/{action_name}/, an object type, or an action): actions/rules/harvest/trip_cap.py (TripCapRule)
Inputs: 
Outputs: 
State read: 
State changed: 
Timing / Frequency: 
Participation: 
Gate: 
Institutional consequence: 
Agent-visible information: 
Verification: VERIFICATION_FAILED (test_round_1_rules.py failed to run)

Requirement: Enforce daily catch cap of 20% of current stock.
Purpose: Limit total daily catch.
Actor: fisher
Level (1/2/3/4): 3
Action this attaches to (which action's own decision or output does this concern): 
Action/Decision: 
Existing owner or new (a rule type under that action's own actions/rules/{action_name}/, an object type, or an action): actions/rules/harvest/daily_cap.py (DailyCapRule)
Inputs: 
Outputs: 
State read: 
State changed: 
Timing / Frequency: 
Participation: 
Gate: 
Institutional consequence: 
Agent-visible information: 
Verification: VERIFICATION_FAILED (test_round_1_rules.py failed to run)

Requirement: Assign rotating treasurer based on first logger.
Purpose: Rotate treasurer role.
Actor: system
Level (1/2/3/4): 3
Action this attaches to (which action's own decision or output does this concern): 
Action/Decision: 
Existing owner or new (a rule type under that action's own actions/rules/{action_name}/, an object type, or an action): actions/rules/harvest/treasurer_assign.py (TreasurerAssignRule)
Inputs: 
Outputs: 
State read: 
State changed: 
Timing / Frequency: 
Participation: 
Gate: 
Institutional consequence: 
Agent-visible information: 
Verification: VERIFICATION_FAILED (test_round_1_rules.py failed to run)

Requirement: Pot balance reviewed and confirmed by all fishers before next day.
Purpose: Ensure agreement on pot.
Actor: all fishers
Level (1/2/3/4): NOT_IMPLEMENTED_THIS_ROUND
Action this attaches to (which action's own decision or output does this concern): 
Action/Decision: 
Existing owner or new (a rule type under that action's own actions/rules/{action_name}/, an object type, or an action): NOT_IMPLEMENTED_THIS_ROUND
Inputs: 
Outputs: 
State read: 
State changed: 
Timing / Frequency: 
Participation: 
Gate: 
Institutional consequence: 
Agent-visible information: 
Verification: NOT_IMPLEMENTED_THIS_ROUND

```json
{
  "requirements": [
    {"requirement": "Fisher logs catch into communal ledger before setting out.", "owner": "NOT_IMPLEMENTED_THIS_ROUND", "verification": "NOT_IMPLEMENTED_THIS_ROUND"},
    {"requirement": "Treasurer totals daily catch at dusk.", "owner": "NOT_IMPLEMENTED_THIS_ROUND", "verification": "NOT_IMPLEMENTED_THIS_ROUND"},
    {"requirement": "Treasurer presents total and 20% threshold to council.", "owner": "NOT_IMPLEMENTED_THIS_ROUND", "verification": "NOT_IMPLEMENTED_THIS_ROUND"},
    {"requirement": "Council votes on excess allocation.", "owner": "NOT_IMPLEMENTED_THIS_ROUND", "verification": "NOT_IMPLEMENTED_THIS_ROUND"},
    {"requirement": "Treasurer records decision and updates pot balance.", "owner": "NOT_IMPLEMENTED_THIS_ROUND", "verification": "NOT_IMPLEMENTED_THIS_ROUND"},
    {"requirement": "Enforce per-trip catch cap of 15 kg.", "owner": "actions/rules/harvest/trip_cap.py", "verification": "VERIFICATION_FAILED"},
    {"requirement": "Enforce daily catch cap of 20% of current stock.", "owner": "actions/rules/harvest/daily_cap.py", "verification": "VERIFICATION_FAILED"},
    {"requirement": "Assign rotating treasurer based on first logger.", "owner": "actions/rules/harvest/treasurer_assign.py", "verification": "VERIFICATION_FAILED"},
    {"requirement": "Pot balance reviewed and confirmed by all fishers before next day.", "owner": "NOT_IMPLEMENTED_THIS_ROUND", "verification": "NOT_IMPLEMENTED_THIS_ROUND"}
  ]
}
```

| requirement | shape | level | owner | verification |
|---|---|---|---|---|
| Fisher logs catch into communal ledger before setting out. | requirement | NOT_IMPLEMENTED_THIS_ROUND | NOT_IMPLEMENTED_THIS_ROUND | NOT_IMPLEMENTED_THIS_ROUND |
| Treasurer totals daily catch at dusk. | requirement | NOT_IMPLEMENTED_THIS_ROUND | NOT_IMPLEMENTED_THIS_ROUND | NOT_IMPLEMENTED_THIS_ROUND |
| Treasurer presents total and 20% threshold to council. | requirement | NOT_IMPLEMENTED_THIS_ROUND | NOT_IMPLEMENTED_THIS_ROUND | NOT_IMPLEMENTED_THIS_ROUND |
| Council votes on excess allocation. | requirement | NOT_IMPLEMENTED_THIS_ROUND | NOT_IMPLEMENTED_THIS_ROUND | NOT_IMPLEMENTED_THIS_ROUND |
| Treasurer records decision and updates pot balance. | requirement | NOT_IMPLEMENTED_THIS_ROUND | NOT_IMPLEMENTED_THIS_ROUND | NOT_IMPLEMENTED_THIS_ROUND |
| Enforce per-trip catch cap of 15 kg. | requirement | 3 | actions/rules/harvest/trip_cap.py | VERIFICATION_FAILED |
| Enforce daily catch cap of 20% of current stock. | requirement | 3 | actions/rules/harvest/daily_cap.py | VERIFICATION_FAILED |
| Assign rotating treasurer based on first logger. | requirement | 3 | actions/rules/harvest/treasurer_assign.py | VERIFICATION_FAILED |
| Pot balance reviewed and confirmed by all fishers before next day. | requirement | NOT_IMPLEMENTED_THIS_ROUND | NOT_IMPLEMENTED_THIS_ROUND | NOT_IMPLEMENTED_THIS_ROUND |
