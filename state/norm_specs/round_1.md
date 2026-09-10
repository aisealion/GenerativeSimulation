# Round 1 Institutional Design Specification

## Policy Summary
Each fisher may take no more than 5 kg per trip, must keep a mandatory 1 kg reserve, records the catch on the communal ledger, and must obey monthly stock measurements that trigger a one-week suspension if below 200 kg.

## Requirements

### R1: Catch Cap (5kg limit)
- **Description**: Each fisher may take no more than 5 kg per trip.
- **Classification**: clear
- **Implementation**: A norm that caps the harvested amount at 5kg per agent per round.
- **Trigger**: When raw_kg > 5kg.
- **Action**: Trim to 5kg, mark as violation with sanction "over_cap".

### R2: Mandatory Reserve (1kg minimum)
- **Description**: Each fisher must keep a mandatory 1 kg reserve.
- **Classification**: clear
- **Implementation**: A norm ensuring each fisher keeps at least 1kg as reserve.
- **Trigger**: When kept_kg < 1kg after all other norms.
- **Action**: If reserve would be violated, this is a violation with sanction "under_reserve".
- **Note**: The reserve is separate from the kept catch - the fisher must have at least 1kg total including reserve.

### R3: Ledger Recording
- **Description**: The fisher records the catch on the communal ledger.
- **Classification**: clear
- **Implementation**: Norm state tracks per-agent catch history (weight, reserve, violations) in the communal ledger.
- **Data tracked**: agent_id, total_weight, reserve_kg, round_number, violations_count.

### R4: Violation Handling (First Offense)
- **Description**: If a fisher reports >5kg or reserve <1kg, the fisher must return 2kg to the communal barrel and receive a gentle reminder.
- **Classification**: clear
- **Implementation**: A norm that handles first-time violations.
- **Trigger**: sanction == "over_cap" or sanction == "under_reserve".
- **Action**: Deduct 2kg from kept_kg (minimum 0), add to communal barrel, increment violation count, note in ledger.
- **Note**: The "communal barrel" is tracked as a shared reserve in norm state.

### R5: Repeated Violation Ban (2nd+ offense)
- **Description**: Repeated violations (the second or subsequent) result in a one-week ban imposed by the council.
- **Classification**: clear
- **Implementation**: A ban norm that triggers on repeated violations.
- **Trigger**: When violation count >= 2 for an agent.
- **Action**: Agent is ineligible to fish for 7 rounds (one week).
- **Ban mechanics**: 
  - `is_eligible()` returns False during ban period.
  - Ban duration: 7 rounds.
  - Ban recorded in ledger.
  - Ban countdown ticks each round via `is_eligible()` call.

### R6: Monthly Stock Measurement
- **Description**: Monthly stock measurements trigger a one-week suspension if below 200 kg.
- **Classification**: clear
- **Implementation**: A round-level norm that checks stock monthly.
- **Trigger**: Every 30 rounds (monthly), check if stock_kg < 200kg.
- **Action**: If triggered, activate community-wide one-week suspension starting next round.

### R7: Community Suspension
- **Description**: One-week suspension effective the next day when stock is below 200kg.
- **Classification**: clear
- **Implementation**: A ban norm that affects all fishers when triggered by monthly measurement.
- **Trigger**: Activated by monthly stock measurement finding stock < 200kg.
- **Action**: All fishers ineligible for 7 rounds.
- **Note**: This is a community-wide suspension, not per-agent.

## Norm Plugin Architecture

Based on the operationalization, the following norm plugins will be created:

1. **catch_cap** (`norms/catch_cap.py`): Enforces 5kg per trip limit.
2. **mandatory_reserve** (`norms/mandatory_reserve.py`): Enforces 1kg minimum reserve.
3. **violation_handler** (`norms/violation_handler.py`): Handles first-offense penalties (2kg return).
4. **repeated_violation_ban** (`norms/repeated_violation_ban.py`): Implements one-week ban for 2nd+ violations.
5. **monthly_stock_suspension** (`norms/monthly_stock_suspension.py`): Implements monthly stock check and community suspension.

## Configuration Order

The norms must be applied in this order:
1. `catch_cap` - Trim over-limit catches first.
2. `mandatory_reserve` - Check reserve compliance after cap.
3. `violation_handler` - Apply penalties for violations.
4. `repeated_violation_ban` - Check eligibility based on violation history.
5. `monthly_stock_suspension` - Check community-wide suspension last.

## State Schema

### Per-Agent State (in `runtime["norms"][key]`)
- `violations`: List of violation records `{round: int, type: str}`.
- `violation_count`: int, total violations.
- `ban_end_round`: int, round when ban expires (if banned).

### Community State
- `communal_barrel_kg`: float, total kg in communal barrel.
- `suspension_end_round`: int, round when community suspension expires.
- `last_stock_check_round`: int, last monthly measurement round.

## Notes

- The "ledger" is implemented as norm state persisted in `runtime["norms"]`.
- The "rotating checks" are simulated through the norm evaluation mechanism itself.
- "Clerk posts in common area" is represented by the norm state being queryable.
- "Council" actions are automated based on the rules.
