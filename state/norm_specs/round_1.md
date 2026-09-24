### R1 — ROLE
Description: A rotating pot keeper among fishers who records contributions.
Agent experience: {"knows": ["They are responsible for recording contributions."], "decides": [], "may_do": [], "may_not_do": [], "remembers": ["Their duty to record until rotation."], "observes": []}
Evidence (verified, not merely claimed):
  - registered role rotating_pot_keeper in state/institution.json
  - wrote prompts/role_directives/rotating_pot_keeper.md
Acceptance tests: test_R1_rotating_pot_keeper_role_is_exclusive PASS

### R2 — ACTION
Description: Fisher weighs their haul.
Agent experience: {"knows": ["Must weigh accurately."], "decides": ["Accurate weighing of their catch."], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - harvest action already exists that enables fishers to weigh haul
Acceptance tests: test_R2_fisher_action_involves_weighing PASS

### R3 — OBJECT
Description: Communal pot holding contributions.
Evidence (verified, not merely claimed):
  - communal pot object type defined in state/institution.json
  - communal pot instance defined in state/objects.json
Acceptance tests: test_R3_communal_pot_object_and_attributes PASS

### R4 — RULE
Description: Calculate 5% of total weight, rounded to nearest 0.5 kg.
Agent experience: {"knows": [], "decides": [], "may_do": [], "may_not_do": ["Contribute less than calculated amount."], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - calculate_contribution rule defined in state/config.json with params percentage=0.05, rounding_interval=0.5
Acceptance tests: test_R4_contribution_calculation_rule_parameters PASS

### R5 — VISIBILITY
Description: Council can see total contributions and identify shortfalls.
Agent experience: {"knows": [], "decides": [], "may_do": [], "may_not_do": [], "remembers": [], "observes": ["Total contributions and shortfalls."]}
Evidence (verified, not merely claimed):
  - VERIFICATION_FAILED: claimed visibility configuration to allow council to access communal pot data, but no such configuration found in state/institution.json, state/config.json or other state files
Acceptance tests: test_R5_council_visibility_to_communal_pot FAIL

### R6 — LIFECYCLE
Description: Revocation period of 7 or 14 days.
Evidence (verified, not merely claimed):
  - VERIFICATION_FAILED: claimed lifecycle system set up for 7-day revocation period, but no revocation system found in state files for a 7 or 14 day period
Acceptance tests: test_R6_revocation_period_lifecycle_exists FAIL