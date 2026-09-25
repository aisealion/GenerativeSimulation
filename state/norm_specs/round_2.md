### R1 — ROLE
Description: Ledger Keeper exists as a role elected weekly by simple majority vote.
Agent experience: 
  - knows: The current Ledger Keeper is known to all fishers.
  - decides: 
  - may_do: Consolidate logs and notify elders of violations.
  - may_not_do: 
  - remembers: 
  - observes: 
Evidence (verified, not merely claimed):
  - registered role ledger_keeper in state/institution.json
  - wrote prompts/role_directives/ledger_keeper.md
Acceptance tests: VERIFICATION_FAILED: Test execution cannot be performed due to access limitations.

### R2 — ROLE
Description: Community Elders role exists to review ledger and enforce compliance.
Agent experience: 
  - knows: Elders' identities and decisions are known.
  - decides: 
  - may_do: 
  - may_not_do: 
  - remembers: 
  - observes: Elders' enforcement actions are visible.
Evidence (verified, not merely claimed):
  - registered role community_elders in state/institution.json
  - wrote prompts/role_directives/community_elders.md
Acceptance tests: VERIFICATION_FAILED: Test execution cannot be performed due to access limitations.

### R3 — ACTION
Description: Ledger Keeper consolidates logs within 24 hours and uploads the summary.
Agent experience: 
  - knows: 
  - decides: When to consolidate and upload logs.
  - may_do: 
  - may_not_do: 
  - remembers: 
  - observes: 
Evidence (verified, not merely claimed):
  - registered action consolidate_and_upload_logs in state/institution.json
  - activated rule lagoon_gate in state/config.json["rules"]["enter_lagoon"]
Acceptance tests: VERIFICATION_FAILED: Test execution cannot be performed due to access limitations.

### R4 — RULE
Description: No fisher may take more than 5% of the lake's stock per trip.
Agent experience: 
  - knows: The 5% limit is known.
  - decides: 
  - may_do: 
  - may_not_do: Take more than 5% per trip.
  - remembers: 
  - observes: 
Evidence (verified, not merely claimed):
  - registered rule type fish_limit_per_trip in state/institution.json
  - implemented rule fish_limit_per_trip in tests/norm_checks/round_2/test_round_2.py
Acceptance tests: VERIFICATION_FAILED: Test execution cannot be performed due to access limitations.

### R5 — RULE
Description: At least one day between fishing trips.
Agent experience: 
  - knows: The required wait period is known.
  - decides: 
  - may_do: 
  - may_not_do: Fish without waiting one day between trips.
  - remembers: 
  - observes: 
Evidence (verified, not merely claimed):
  - registered rule type waiting_period_between_fishing_trips in state/institution.json
  - implemented rule waiting_period_between_fishing_trips in tests/norm_checks/round_2/test_round_2.py
Acceptance tests: VERIFICATION_FAILED: Test execution cannot be performed due to access limitations.

### R6 — ACTION
Description: Elders review the ledger and enforce compliance.
Agent experience: 
  - knows: 
  - decides: How to enforce compliance based on ledger review.
  - may_do: 
  - may_not_do: 
  - remembers: 
  - observes: 
Evidence (verified, not merely claimed):
  - registered action review_ledger_and_enforce_compliance in state/institution.json
  - activated rule lagoon_gate in state/config.json["rules"]["enter_lagoon"]
Acceptance tests: VERIFICATION_FAILED: Test execution cannot be performed due to access limitations.

### R7 — OBJECT
Description: Community fund for deposited fines.
Agent experience: 
  - knows: 
  - decides: 
  - may_do: 
  - may_not_do: 
  - remembers: 
  - observes: 
Evidence (verified, not merely claimed):
  - registered object type community_fund in state/institution.json
  - created file state/objects/community_fund.json
Acceptance tests: VERIFICATION_FAILED: Test execution cannot be performed due to access limitations.

### R8 — VISIBILITY
Description: All fishers can see the ledger after upload.
Agent experience: 
  - knows: 
  - decides: 
  - may_do: 
  - may_not_do: 
  - remembers: 
  - observes: The ledger entries are visible.
Evidence (verified, not merely claimed):
  - activated visibility rule for ledger keeper's logs in state/config.json["visibility"]["ledger_keeper_logs"]
  - NOT_IMPLEMENTED_THIS_ROUND: Visibility check for ledger keeper logs has not been fully implemented
Acceptance tests: VERIFICATION_FAILED: Test execution cannot be performed due to access limitations.

### R9 — LIFECYCLE
Description: Ledger Keeper role rotates weekly.
Agent experience: 
  - knows: 
  - decides: 
  - may_do: 
  - may_not_do: 
  - remembers: 
  - observes: 
Evidence (verified, not merely claimed):
  - activated lifecycle rule for ledger keeper rotation in state/config.json["lifecycle"]["ledger_keeper"]
  - NOT_IMPLEMENTED_THIS_ROUND: Ledger keeper rotation lifecycle has not been fully implemented
Acceptance tests: VERIFICATION_FAILED: Test execution cannot be performed due to access limitations.
