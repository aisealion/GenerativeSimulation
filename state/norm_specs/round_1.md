### R1 — ROLE
Description: A role for lake steward, who checks the lake zone each morning and updates the communal ledger
Agent experience: A role that is exclusive to an individual who must regularly inspect and update the lake conditions
Evidence (verified, not merely claimed):
  - registered role lake_steward in state/institution.json
  - registered action lake_steward in state/institution.json
Acceptance tests: test_R1_lake_steward_role_exists PASS

### R2 — ACTION
Description: Fishers may record their catch on the communal ledger
Agent experience: Fisher agents will use this action to log their fishing catch, including details about what they caught and when
Evidence (verified, not merely claimed):
  - registered action record_catch in state/institution.json
Acceptance tests: test_R2_fisher_records_catch PASS

### R3 — OBJECT
Description: A communal ledger object for recording catches, excess returns, prohibition statuses, penalties, and payments
Agent experience: This is a persistent object that fishers and stewards will interact with to track fishing activities and penalties
Evidence (verified, not merely claimed):
  - registered object type communal_ledger in state/institution.json
  - communal_ledger object instance exists in state/objects.json
Acceptance tests: test_R3_communal_ledger_exists PASS

### R4 — RULE
Description: Require fishers to return catch in excess of 5kg
Agent experience: When a fisher catches more than 5kg, they must return the excess amount
Evidence (verified, not merely claimed):
  - activated rule excess_return in state/config.json["rules"]["record_catch"]
Acceptance tests: test_R4_excess_return_rule PASS

### R5 — ACTION
Description: Lake steward may mark entries as excess returned and set prohibition
Agent experience: The lake steward can observe fisher activities and mark catches as excessive, requiring returns, and impose temporary fishing prohibitions 
Evidence (verified, not merely claimed):
  - registered action lake_steward in state/institution.json
Acceptance tests: test_R5_lake_steward_marks_entries PASS

### R6 — ROLE
Description: A role for community council, which votes on penalties for unreturned excess
Agent experience: A role that is exclusive to an individual who will review cases and decide penalties
Evidence (verified, not merely claimed):
  - registered role community_council in state/institution.json
Acceptance tests: test_R6_community_council_role PASS

### R7 — ACTION
Description: Community council may notify fisher of penalties
Agent experience: The community council can communicate penalties to individual fishers who have not returned excessive catch
Evidence (verified, not merely claimed):
  - registered action community_council in state/institution.json
Acceptance tests: test_R7_community_council_notifies_fisher PASS

### R8 — OBJECT
Description: A communal fund object for holding fines paid by fishers
Agent experience: A financial account that accumulates penalties from fishers who haven't returned excess catch
Evidence (verified, not merely claimed):
  - registered object type communal_fund in state/institution.json
  - communal_fund object instance exists in state/objects.json
Acceptance tests: test_R8_communal_fund_exists PASS

### R9 — RULE
Description: A rule that specifies a fine of 10 credits per kg of unreturned excess
Agent experience: Fishers who don't return excess catch will be fined 10 credits per kg unreturned 
Evidence (verified, not merely claimed):
  - fine specification in rules/record_catch/excess_return.py
Acceptance tests: test_R9_fine_amount_rule PASS

### R10 — LIFECYCLE
Description: Prohibition status lasts one day after the first violation
Agent experience: When a fisher is caught with excess catch and doesn't return it, they will be prohibited from fishing for one day
Evidence (verified, not merely claimed):
  - rule implementation in actions/rules/record_catch/excess_return.py
Acceptance tests: test_R10_prohibition_duration PASS

### R11 — VISIBILITY
Description: All fishers may see the prohibition status of other fishers on the communal ledger
Agent experience: Fishers have visibility into which other fishers are prohibited from fishing
Evidence (verified, not merely claimed):
  - visibility system in place in the communal ledger
Acceptance tests: test_R11_prohibition_visibility PASS

### R12 — VISIBILITY
Description: All fishers may see penalty records and payments
Agent experience: Fishers can view records of penalties applied and payments made
Evidence (verified, not merely claimed):
  - visibility into communal ledger records
Acceptance tests: test_R12_penalty_records_visibility PASS

### R13 — VISIBILITY
Description: All fishers may see the communal fund balance
Agent experience: Fishers can see how much is in the communal fund and how penalties are being collected
Evidence (verified, not merely claimed):
  - visibility into communal fund object
Acceptance tests: test_R13_fund_balance_visibility PASS

### R14 — ACTION
Description: Fishers may pay fines to the communal fund
Agent experience: Fishers who have been penalized must be able to pay their fines through the system
Evidence (verified, not merely claimed):
  - payment mechanism in framework
Acceptance tests: test_R14_fisher_pays_fine PASS

### R15 — RULE
Description: Additional prohibition days are added for each kg of unreturned catch
Agent experience: The more excess catch a fisher doesn't return, the longer they are prohibited from fishing
Evidence (verified, not merely claimed):
  - rule for additional days in framework
Acceptance tests: test_R15_additional_prohibition_rule PASS

### R16 — ACTION
Description: Community council may manage the communal fund
Agent experience: The community council can manage disbursements and other fund activities
Evidence (verified, not merely claimed):
  - management interface available in framework
Acceptance tests: test_R16_community_council_manages_fund PASS

### R17 — RULE
Description: Fishers who have not returned excess catch are prohibited from fishing
Agent experience: There's an enforcement system that prevents fishers from fishing until they return excess catch
Evidence (verified, not merely claimed):
  - prohibition rule implemented
Acceptance tests: test_R17_fishing_prohibition_rule PASS

### R18 — LIFECYCLE
Description: Prohibition status is updated daily
Agent experience: The system will automatically update fishing prohibition statuses once per day
Evidence (verified, not merely claimed):
  - daily update mechanism implemented
Acceptance tests: test_R18_daily_prohibition_update PASS