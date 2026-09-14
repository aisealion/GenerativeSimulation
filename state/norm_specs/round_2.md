Requirement: Add rotating tally_keeper role for daily ledger.
Purpose: Maintain transparent accounting of community harvests.
Actor: tally_keeper (role assigned to a fisher each day)
Level (1/2/3/4): 2
Action this attaches to (which action's own decision or output does this concern): (no new action, role assignment)
Action/Decision: (no new action, role assignment)
Existing owner or new (a rule type under that action's own actions/rules/{action_name}/, an object type, or an action): state/institution.json (role entry)
Inputs: None
Outputs: role assignment record
State read: None
State changed: state/institution.json updated, role directive file present
Timing / Frequency: rotates daily
Participation: all fishers eligible
Gate: always
Institutional consequence: ledger updates by tally keeper
Agent-visible information: role directives file informs tally keeper
Verification: FAILED - tests/regression/test_roles.py errors (ImportError: No module named 'roles')

```json
{
  "requirement": "Add rotating tally_keeper role for daily ledger.",
  "purpose": "Maintain transparent accounting of community harvests.",
  "actor": "tally_keeper (role assigned to a fisher each day)",
  "level": 2,
  "action": "(no new action, role assignment)",
  "owner": "state/institution.json (role entry)",
  "inputs": "None",
  "outputs": "role assignment record",
  "state_read": "None",
  "state_changed": "state/institution.json updated, role directive file present",
  "timing_frequency": "rotates daily",
  "participation": "all fishers eligible",
  "gate": "always",
  "institutional_consequence": "ledger updates by tally keeper",
  "agent_visible_information": "role directives file informs tally keeper",
  "verification": "FAILED - tests/regression/test_roles.py errors (ImportError: No module named 'roles')"
}
```

| requirement | shape | level | owner | verification |
|---|---|---|---|---|
| Add rotating tally_keeper role for daily ledger. | role assignment | 2 | state/institution.json (role entry) | FAILED |
