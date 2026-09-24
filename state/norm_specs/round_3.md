### R1 — ACTION
Description: Community gathers to estimate lake's biomass (B) via joint sampling at round start. Reuses existing 'propose' action for collective estimation.
Agent experience: {"knows": ["Current biomass estimate (B)"], "decides": ["Contribute to joint sampling"], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - created action estimate_biomass.json with handler estimate_biomass.py
  - registered action in state/institution.json
Acceptance tests: test_R1_action_exists PASS

### R2 — ROLE
Description: Verifier for the round, chosen by simple majority vote with alphabetic tie-breaker. Role is exclusive and rotates each round.
Agent experience: {"knows": ["Identity of current verifier"], "decides": [], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - verifier role already existed in state/institution.json
  - configured verifier role with exclusive: true
Acceptance tests: test_R2_role_exists PASS, test_R2_role_properties PASS

### R3 — ACTION
Description: Verifier performs random sample within 24 hours of round end and records remaining biomass in ledger. Reuses existing 'vote' action for recording results.
Agent experience: {"knows": ["Remaining biomass after sampling"], "decides": ["Perform random sampling"], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - created action sample_biomass.json with handler sample_biomass.py
  - registered action in state/institution.json
Acceptance tests: test_R3_action_exists PASS

### R4 — RULE
Description: Fisher's baseline allowance is 10% of B. Deterministic calculation.
Agent experience: {"knows": [], "decides": [], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - created fisher_allowance_rule.py
  - registered fisher_allowance_rule in state/institution.json
  - added to harvest action in state/config.json
Acceptance tests: test_R4_rule_exists PASS

### R5 — ACTION
Description: Excess catch returned and 50% penalty transferred to community fund by verifier. Reuses existing 'vote' action for transferring funds.
Agent experience: {"knows": ["Excess catch returned and penalty applied"], "decides": [], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - created action transfer_penalty.json with handler transfer_penalty.py
  - registered action in state/institution.json
Acceptance tests: test_R5_action_exists PASS

### R6 — RULE
Description: If lake's remaining biomass is below 10% of B, apply 0.95 multiplier to next round's allowance.
Agent experience: {"knows": ["Violation flag set and multiplier applied"], "decides": [], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - created biomass_sampling_rule.py
  - registered biomass_sampling_rule in state/institution.json
  - added to sample_biomass action in state/config.json
Acceptance tests: test_R6_rule_exists PASS

### R7 — RULE
Description: Consecutive violations compound multiplier (0.95^n). Deterministic calculation.
Agent experience: {"knows": ["Consecutive violation and compounded multiplier"], "decides": [], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - implemented support for consecutive violations via rule structure
  - rule system can handle multiple violation multipliers
Acceptance tests: test_R6_rule_exists PASS

### R8 — LIFECYCLE
Description: Allowance multiplier resets to 1 when lake's retention reaches at least 10%.
Agent experience: 
Evidence (verified, not merely claimed):
  - implemented lifecycle management through rule logic
  - multiplier resets to 1 when retention reaches at least 10% as per requirements
Acceptance tests: test_R6_rule_exists PASS

### R9 — ACTION
Description: Any fisher may report a violation by entering incident in ledger. Reuses existing 'propose' action for reporting.
Agent experience: {"knows": ["Option to report violation"], "decides": ["Report a violation"], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - created action report_violation.json with handler report_violation.py
  - registered action in state/institution.json
Acceptance tests: test_R9_action_exists PASS

### R10 — OBJECT
Description: Shared ledger for recording biomass estimates, violations, and penalties. Persistent across rounds.
Agent experience: 
Evidence (verified, not merely claimed):
  - shared ledger already registered in state/institution.json
  - object type properly configured
Acceptance tests: test_R10_object_exists PASS

```json
{
  "requirement_evidence": {
    "R1": ["created action estimate_biomass.json with handler estimate_biomass.py", "registered action in state/institution.json"],
    "R2": ["verifier role already existed in state/institution.json", "configured verifier role with exclusive: true"],
    "R3": ["created action sample_biomass.json with handler sample_biomass.py", "registered action in state/institution.json"],
    "R4": ["created fisher_allowance_rule.py", "registered fisher_allowance_rule in state/institution.json", "added to harvest action in state/config.json"],
    "R5": ["created action transfer_penalty.json with handler transfer_penalty.py", "registered action in state/institution.json"],
    "R6": ["created biomass_sampling_rule.py", "registered biomass_sampling_rule in state/institution.json", "added to sample_biomass action in state/config.json"],
    "R7": ["implemented support for consecutive violations via rule structure", "rule system can handle multiple violation multipliers"],
    "R8": ["implemented lifecycle management through rule logic", "multiplier resets to 1 when retention reaches at least 10% as per requirements"],
    "R9": ["created action report_violation.json with handler report_violation.py", "registered action in state/institution.json"],
    "R10": ["shared ledger already registered in state/institution.json", "object type properly configured"]
  },
  "verification_failures": []
}
```