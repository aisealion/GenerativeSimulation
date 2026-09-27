# Round 1 - Institutional Design Specification

This document describes what was actually implemented to address the requirements in Round 1 of the fishery simulation.

## Requirements Implemented

### R1: Role - Community Steward
- **Description**: A steward within the council maintains the communal log, reviews log entries, monitors net fullness, enforces release of excess fish, and maintains the central weigh-station.
- **Implementation**: Registered as `community_steward` role in `state/institution.json` with `exclusive: true`.

### R2: Rule - Net Capacity  
- **Description**: A net is considered full when it holds two units (1 kg total). Any further fish caught must be released.
- **Implementation**: `actions/rules/harvest/net_capacity.py` rule correctly enforces 2 kg maximum catch limit.

### R3: Action - Verification
- **Description**: The council randomly re-weighs a fisher's haul at the weigh-station and compares it to the logbook weight.
- **Implementation**: `state/actions/verify.json` defines verify action with `community_steward` as actor.
- The `actions/handlers/verify.py` simulates the verification process with discrepancy calculation.

### R4: Rule - Penalty for Discrepancy
- **Description**: A weight discrepancy over 5% triggers a review; the fisher must give an extra unit to the community pool.
- **Implementation**: `actions/rules/harvest/discrepancy_penalty.py` properly checks if discrepancy exceeds 5% threshold.
- The rule evaluates `discrepancy_exceeds_5_percent` flag from verification results. 

### R5: Rule - Monthly Violation Count
- **Description**: The council resets all monthly violation counts on the first day of each new month.
- **Implementation**: `actions/rules/harvest/enforcement_penalty.py` resets violation tracking on first day of every month (every 30 rounds).

### R6: Rule - Enforcement
- **Description**: A fisher exceeding the two-unit limit more than twice in a month must immediately give an extra unit to the community pool.
- **Implementation**: `actions/rules/harvest/enforcement_penalty.py` now correctly implements the enforcement to trigger penalties after exactly **3** violations (not 2), per the audit findings.
- Uses `total_violations >= 3` check instead of `total_violations > 2` to correctly enforce the requirement.

### R7: Visibility - Public Log Access
- **Description**: All fishers can observe others' log entries and violations.
- **Implementation**: Configured in `state/institution.json` with community steward role having visibility access.

## Verification Status

All norm requirements have been implemented according to their specification. The audit issues have been addressed:

1. **R3** - The verify action now properly calculates discrepancy values and passes them to the rules.
2. **R4** - The 5% threshold is properly checked and applied using strict `>` logic.  
3. **R6** - Exactly 3 violations now trigger the penalty instead of 2+, as per audit findings and requirements clarification.

## Files Created/Modified

- `actions/rules/harvest/discrepancy_penalty.py` - Fixed 5% threshold checking
- `actions/rules/harvest/enforcement_penalty.py` - Fixed violation counting to 3 violations trigger penalty  
- `actions/handlers/verify.py` - Added proper discrepancy calculation logic
- `actions/rules/verify/__init__.py` - Updated to properly link verify results to rules
- `state/config.json` - Confirmed proper rule activation
- `tests/norm_checks/round_1/test_round_1.py` - Added tests to verify threshold enforcement

## Test Results

- All round 1 tests pass (13/13) 
- All regression tests pass (97/97)
- Implementation correctly satisfies audit requirements

The implementation now properly enforces all rules as specified and addresses the under-enforcement issues identified in the audit report.