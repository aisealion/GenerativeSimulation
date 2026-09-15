Requirement: Fisher logs catch into communal ledger before setting out.
Purpose: Record each fisher's catch in the communal ledger.
Actor: fisher
Level: 3
Action this attaches to: harvest
Action/Decision: after_agent (TripCapRule, DailyCapRule)
Existing owner or new: actions/rules/harvest/trip_cap.py, actions/rules/harvest/daily_cap.py
Inputs: catch slip, weight, ID verification
Outputs: ledger entry, note
State read: none
State changed: communal_ledger.balance_kg, record_entry.harvested_kg
Timing/Frequency: per trip
Participation: all fishers
Gate: council member verification of ID against suspension list
Institutional consequence: fine for excess, deposit excess to ledger
Agent-visible information: notes on record
Verification: tests/norm_checks/test_round_1_rules.py

Requirement: Enforce per-trip catch cap of 10 kg.
Purpose: Limit fisher's trip catch.
Actor: fisher
Level: 3
Action this attaches to: harvest
Action/Decision: after_agent (TripCapRule)
Existing owner or new: actions/rules/harvest/trip_cap.py
Inputs: harvested_kg
Outputs: possibly reduced harvested_kg, note, ledger fine
State read: none
State changed: record_entry.harvested_kg, communal_ledger.balance_kg
Timing/Frequency: per trip
Participation: fisher
Gate: none
Institutional consequence: fine 5 kg for excess
Verification: tests/norm_checks/test_round_1_rules.py

Requirement: Enforce daily catch cap of 100 kg.
Purpose: Limit total daily community catch.
Actor: fisher
Level: 3
Action this attaches to: harvest
Action/Decision: after_agent (DailyCapRule)
Existing owner or new: actions/rules/harvest/daily_cap.py
Inputs: harvested_kg per agent
Outputs: possibly reduced harvested_kg, note, deposit excess to ledger
State read: rule_state daily total
State changed: record_entry.harvested_kg, communal_ledger.balance_kg
Timing/Frequency: daily
Participation: all fishers
Gate: none
Institutional consequence: excess deposited to communal ledger
Verification: tests/norm_checks/test_round_1_rules.py

Requirement: Assign rotating treasurer based on first logger.
Purpose: Rotate treasurer role.
Actor: system
Level: 3
Action this attaches to: harvest
Action/Decision: after_action (TreasurerAssignRule)
Existing owner or new: actions/rules/harvest/treasurer_assign.py
Inputs: first logger id
Outputs: treasurer role assignment
State read: rule_state first_logger
State changed: fluent treasurer assignment
Timing/Frequency: daily
Participation: system
Gate: none
Institutional consequence: treasurer assigned for next day
Verification: tests/norm_checks/test_round_1_rules.py