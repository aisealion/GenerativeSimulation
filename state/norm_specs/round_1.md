# Round 1 Norm Specification

## Requirement: Each trip: fisherman records total catch.
Purpose: To maintain a record of each fisher's catch amount for quota management.
Actor: Fisher
Level (1/2/3/4): 1
Action this attaches to (which action's own decision or output does this concern): harvest
Action/Decision: 
Existing owner or new (a rule type under that action's own actions/rules/{action_name}/, an object type, or an action): actions/rules/harvest/record_catch.py
Inputs: harvested_kg
Outputs: recorded_catch
State read: fisher[agent_id]["harvested_kg"]
State changed: fisher[agent_id]["harvested_kg"]
Timing / Frequency: Each harvest trip
Participation: All fishers
Gate: true
Institutional consequence: Fishers' catch amounts are tracked for quota enforcement
Agent-visible information: harvest amount
Verification: test_trip_record_and_deposit

## Requirement: If catch >12 kg, keep 12 kg and deposit excess.
Purpose: To implement the quota system where fishers can only keep 12kg and must deposit any excess.
Actor: Fisher
Level (1/2/3/4): 1
Action this attaches to (which action's own decision or output does this concern): harvest
Action/Decision: 
Existing owner or new (a rule type under that action's own actions/rules/{action_name}/, an object type, or an action): actions/rules/harvest/deposit_excess.py
Inputs: harvested_kg
Outputs: deposit_amount, net_personalcatch
State read: fisher[agent_id]["harvested_kg"]
State changed: None
Timing / Frequency: Each harvest trip
Participation: Fishers with catch > 12kg
Gate: true
Institutional consequence: Enforcement of 12kg quota limit and deposit tracking
Agent-visible information: deposit amount, personal catch
Verification: test_trip_record_and_deposit

## Requirement: Deposit slip is handed to council member at end of day.
Purpose: To process deposits of excess fish at the end of each day.
Actor: Fisher
Level (1/2/3/4): 4
Action this attaches to (which action's own decision or output does this concern): harvest
Action/Decision: deposit
Existing owner or new (a rule type under that action's own actions/rules/{action_name}/, an object type, or an action): state/actions/deposit.json
Inputs: None
Outputs: None
State read: fisher[agent_id]["harvested_kg"]
State changed: None
Timing / Frequency: End of day
Participation: All fishers_with_excess_catch
Gate: true
Institutional consequence: Daily processing of excess fish deposits
Agent-visible information: deposit amount
Verification: test_deposit_slip_handling

## Files Built

1. **actions/rules/harvest/record_catch.py** - Implements the "Each trip: fisherman records total catch" requirement (Level 1)
2. **actions/rules/harvest/deposit_excess.py** - Implements the "If catch >12 kg, keep 12 kg and deposit excess" requirement (Level 1)  
3. **state/actions/deposit.json** - Implements the "Deposit slip is handed to council member at end of day" requirement (Level 4)

## Implementation Details

### Requirement 1: Record Catch
The `RecordCatchRule` in `actions/rules/harvest/record_catch.py` correctly implements the requirement to record the total catch amount for each fisher on each trip. It stores the catch amount in the fisher's harvested_kg field and returns the recorded catch value for agent visibility.

### Requirement 2: Deposit Excess
The `DepositExcessRule` in `actions/rules/harvest/deposit_excess.py` correctly implements the requirement to keep 12 kg and deposit excess fish when catch exceeds 12 kg. It calculates the deposit amount as `max(0.0, harvested_kg - 12.0)` and returns both the deposit amount and net personal catch values, properly calculating the net catch considering a 1 kg sustenance requirement.

### Requirement 3: Deposit Slip Submission
The `deposit.json` action in `state/actions/deposit.json` correctly implements the requirement that the deposit slip is handed to a council member at the end of the day. It defines an action with proper scheduling (end of day), participation rules, and execution handler that aligns with the deposit slip handling requirement.

All requirements have been implemented according to the specifications in the checklist.

```json
{
  "requirement": "Each trip: fisherman records total catch.",
  "shape": "Rule",
  "level": 1,
  "owner": "actions/rules/harvest/record_catch.py",
  "verification": "test_trip_record_and_deposit"
}
{
  "requirement": "If catch >12 kg, keep 12 kg and deposit excess.",
  "shape": "Rule",
  "level": 1,
  "owner": "actions/rules/harvest/deposit_excess.py",
  "verification": "test_trip_record_and_deposit"
}
{
  "requirement": "Deposit slip is handed to council member at end of day.",
  "shape": "Action",
  "level": 4,
  "owner": "state/actions/deposit.json",
  "verification": "test_deposit_slip_handling"
}
```