### R1 — ROLE
Description: The Fish Ledger Keeper role exists to manage the community fish bank, enforce harvesting limits, and restore biomass thresholds.
Agent experience: {"knows": ["The current lake biomass before each round", "Which fishers have exceeded catch limits", "The deficit calculation when biomass falls below 10%", "The status of the community fish bank"], "decides": ["When to release fish from the community bank", "Whether a fisher should be banned for a round"], "may_do": [], "may_not_do": [], "remembers": ["Previous biomass levels and their impact on current decisions", "Repeat offenders of catch limits"], "observes": []}
Evidence (verified, not merely claimed):
  - registered role fish_ledger_keeper in state/institution.json
Acceptance tests: test_R1_role_exists PASS

### R2 — ACTION
Description: The Fish Ledger Keeper records the lake's pre-round biomass.
Agent experience: {"knows": [], "decides": ["The recorded pre-round biomass value"], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - action record_pre_round_biomass in state/institution.json
Acceptance tests: test_R2_compliant_record_biomass PASS

### R3 — ACTION
Description: Each fisher logs their catch. If a catch exceeds 10% of the lake's biomass, excess is deposited into the community bank and the fisher is flagged.
Agent experience: {"knows": ["The 10% catch limit of current biomass"], "decides": ["Whether to log their catch"], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - action record_catch in state/institution.json
Acceptance tests: test_R3_fisher_catch_log PASS

### R4 — RULE
Description: A fisher's catch cannot exceed 10% of the lake's current biomass.
Agent experience: {"knows": [], "decides": [], "may_do": [], "may_not_do": ["Harvest more than 10% of the lake's biomass"], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - rule catch_limit_rule defined in state/institution.json
Acceptance tests: test_R4_catch_limit_rule PASS

### R5 — ACTION
Description: The Fish Ledger Keeper calculates the lake's remaining biomass after all trips.
Agent experience: {"knows": [], "decides": ["The calculated remaining biomass value"], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - action calculate_remaining_biomass in state/institution.json
Acceptance tests: test_R5_calculate_remaining_biomass PASS

### R6 — RULE
Description: If the remaining biomass is below 10% of pre-round biomass, calculate deficit.
Agent experience: {"knows": [], "decides": [], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - rule deficit_calculation_rule defined in state/institution.json
Acceptance tests: test_R6_deficit_calculation PASS

### R7 — ACTION
Description: The Fish Ledger Keeper releases fish from the community bank equal to the deficit.
Agent experience: {"knows": [], "decides": ["How much fish to release from the bank"], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - action release_fish in state/institution.json
Acceptance tests: test_R7_release_from_bank PASS

### R8 — OBJECT
Description: The community fish bank holds deposited fish from over-limits and releases to restore biomass.
Agent experience: {"knows": [], "decides": [], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - object type community_fish_bank in state/institution.json
Acceptance tests: test_R8_community_fish_bank_exists PASS

### R9 — ACTION
Description: The Fish Ledger Keeper updates the Fish Ledger with deposits, releases, and flags.
Agent experience: {"knows": [], "decides": ["What entries to record on the Fish Ledger"], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - action update_fish_ledger in state/institution.json
Acceptance tests: test_R9_update_fish_ledger PASS

### R10 — ACTION
Description: The Fish Ledger Keeper issues a one-round fishing ban to violating fishers.
Agent experience: {"knows": [], "decides": ["Which fishers to ban for a round"], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - action ban_fisher in state/institution.json
Acceptance tests: test_R10_ban_violating_fishers PASS

### R11 — RULE
Description: Update the community fish bank balance after each release.
Agent experience: {"knows": [], "decides": [], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - rule bank_balance_update_rule defined in state/institution.json
Acceptance tests: test_R11_bank_balance_update PASS

### R12 — OBJECT
Description: The Fish Ledger records all deposits, releases, and enforcement actions.
Agent experience: {"knows": [], "decides": [], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
Evidence (verified, not merely claimed):
  - object type fish_ledger in state/institution.json
Acceptance tests: test_R12_fish_ledger_exists PASS

### R13 — VISIBILITY
Description: All ledger entries are publicly available to all fishers.
Agent experience: {"knows": [], "decides": [], "may_do": [], "may_not_do": [], "remembers": [], "observes": ["All entries in the Fish Ledger"]}
Evidence (verified, not merely claimed):
  - Fish Ledger object entries visible to all fishers via visibility configuration in state/institution.json
Acceptance tests: test_R13_ledger_public_visibility PASS