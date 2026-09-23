### R1 — OBJECT
Description: A shared ledger for recording catch weight and reserve deposits, with an associated communal bin and scale.
Agent experience: 
  - The communal ledger is visible to all fishers after each trip.
Evidence (verified, not merely claimed):
  - registered object_type communal_ledger in state/institution.json
  - created state/objects/communal_ledger.json
  - wrote prompts/object_prompts/communal_ledger.md
Acceptance tests: test_R1_visibility_check PASS

### R2 — ROLE
Description: Bin guard role, assigned alphabetically from the community roster with equal rotation among fishers.
Agent experience: 
  - Who is the current bin guard.
  - Their own duty status as bin guard.
  - Previous guards to ensure fair rotation.
Evidence (verified, not merely claimed):
  - registered role bin_guard in state/institution.json
  - activated rule bin_guard_rotation in state/config.json["rules"]["bin_guard"]
  - created state/roles/bin_guard.json
  - wrote prompts/role_directives/bin_guard.md
Acceptance tests: test_R2_guard_assignment_check PASS

### R3 — ACTION
Description: Verify ledger matches bin weight, call vote if mismatch, enforce penalty based on majority decision.
Agent experience: 
  - The proper procedure for verification and voting.
  - Whether to call a vote.
  - Whether to enforce the penalty.
  - Previous violations and penalties for future decisions.
Evidence (verified, not merely claimed):
  - registered action bin_verification in state/institution.json
  - created state/actions/bin_verification.json
  - wrote prompts/action_prompts/bin_verification.md
Acceptance tests: test_R3_verification_penalty_vote PASS

### R4 — RULE
Description: Limit next trip catch to 8kg if penalty enforced.
Agent experience: 
  - Take more than 8kg on the next trip if penalized.
Evidence (verified, not merely claimed):
  - activated rule catch_limit_enforcement in state/config.json["rules"]["catch_limit"]
  - registered rule_type catch_limit_enforcement in state/institution.json
Acceptance tests: test_R4_enforce_8kg_limit PASS

### R5 — LIFECYCLE
Description: Ensure each fisher performs guard duty equally over time.
Evidence (verified, not merely claimed):
  - activated rule bin_guard_rotation in state/config.json["rules"]["bin_guard"]
  - registered rule_type bin_guard_rotation in state/institution.json
Acceptance tests: test_R5_fair_rotation PASS

### R6 — VISIBILITY
Description: All fishers can see ledger entries after each trip.
Agent experience: 
  - Ledger entries are posted immediately after each trip.
Evidence (verified, not merely claimed):
  - activated visibility communal_ledger in state/config.json["visibility"]["communal_ledger"]
  - registered object_type communal_ledger in state/institution.json
Acceptance tests: test_R6_visibility_check PASS

```json
{
  "requirement_evidence": {
    "R1": [
      "registered object_type communal_ledger in state/institution.json",
      "created state/objects/communal_ledger.json",
      "wrote prompts/object_prompts/communal_ledger.md"
    ],
    "R2": [
      "registered role bin_guard in state/institution.json",
      "activated rule bin_guard_rotation in state/config.json[\"rules\"][\"bin_guard\"]",
      "created state/roles/bin_guard.json",
      "wrote prompts/role_directives/bin_guard.md"
    ],
    "R3": [
      "registered action bin_verification in state/institution.json",
      "created state/actions/bin_verification.json",
      "wrote prompts/action_prompts/bin_verification.md"
    ],
    "R4": [
      "activated rule catch_limit_enforcement in state/config.json[\"rules\"][\"catch_limit\"]",
      "registered rule_type catch_limit_enforcement in state/institution.json"
    ],
    "R5": [
      "activated rule bin_guard_rotation in state/config.json[\"rules\"][\"bin_guard\"]",
      "registered rule_type bin_guard_rotation in state/institution.json"
    ],
    "R6": [
      "activated visibility communal_ledger in state/config.json[\"visibility\"][\"communal_ledger\"]",
      "registered object_type communal_ledger in state/institution.json"
    ]
  },
  "verification_failures": []
}
```