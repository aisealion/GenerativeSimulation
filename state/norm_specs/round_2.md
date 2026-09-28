# Round 2 Norm Specification

## Requirement R8: reserve_authorize action

### Evidence
- Action `reserve_authorize` is registered in `state/institution.json`
- Handler `actions/handlers/reserve_authorize.py` exists and implements the action logic correctly
- The handler properly accesses the `surplus_pool` object via `ctx.objects.read()`
- Action specification exists in `state/actions/reserve_authorize.json`

### Verification
- `test_R8_reserve_authorize_action_registered` → PASS
- `test_R8_reserve_authorize_action_spec_exists` → PASS  
- `test_R8_reserve_authorize_action_handler_exists` → PASS
- `test_R8_reserve_authorize_action_handler_functional` → PASS
- `test_R8_reserve_authorize_structured` → PASS
- `test_R8_reserve_authorize_functional_structure` → PASS

## Requirement R9: surplus_distribution action

### Evidence
- Action `surplus_distribution` is registered in `state/institution.json`
- Handler `actions/handlers/surplus_distribution.py` exists and implements the action logic correctly  
- The handler properly accesses the `surplus_pool` object via `ctx.objects.read()`
- Action specification exists in `state/actions/surplus_distribution.json`

### Verification
- `test_R9_surplus_distribution_action_registered` → PASS
- `test_R9_surplus_distribution_action_spec_exists` → PASS
- `test_R9_surplus_distribution_action_handler_exists` → PASS
- `test_R9_surplus_distribution_action_handler_functional` → PASS
- `test_R9_surplus_distribution_structured` → PASS
- `test_R9_surplus_distribution_functional_structure` → PASS

## Requirement R12: council_member role

### Evidence
- Role `council_member` is registered in `state/institution.json`
- Prompt directive exists in `prompts/role_directives/council_member.md`
- Role assigned to agents in simulation

### Verification
- `test_R8_council_member_role_registered` → PASS

## Requirement R10 & R11: object types

### Evidence
- Object type `surplus_pool` is registered in `state/institution.json`  
- Object type `dock_ledger` is registered in `state/institution.json`
- Object type specification exists in `state/object_types/surplus_pool.json`
- Object instance declared in `state/objects.json`

### Verification
- `test_R9_object_types_registered` → PASS
- `test_R8_R9_files_exist` → PASS

## Requirement R13: harvest_tracking rule

### Evidence
- Rule type `harvest_tracking` is registered in `state/institution.json`
- Rule handler exists in `actions/rules/harvest_tracking/handler.py`
- Rule is active for the harvest action

### Verification
- `test_R13_harvest_tracking_rule_registered` → PASS
- `test_R13_harvest_tracking_rule_applied` → PASS

## Requirement R14: reserve_allocation rule

### Evidence
- Rule type `reserve_allocation` is registered in `state/institution.json`
- Rule handler exists in `actions/rules/reserve_allocation/handler.py`
- Rule is active for the harvest action

### Verification
- `test_R14_reserve_allocation_rule_registered` → PASS
- `test_R14_reserve_allocation_rule_applied` → PASS

## Verification Failures
None