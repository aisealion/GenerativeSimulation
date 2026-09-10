# Round 3 Institutional Design Specification

## Policy Summary
No fisher may take more than 12% of the lake's current stock per trip; each fisher must keep a personal reserve of at least 1 kg; any excess over the 12% limit must be returned to the lake; violations trigger a fine equal to 2% of the lake's stock at the moment of the infraction, paid to the community by the lake-watcher.

## Requirements Analysis

### R1: Lake-Watcher Role (Stock Estimation & Verification)
- **Description**: The lake-watcher estimates stock before each trip and cross-checks each fisher's ledger at trip end, verifying that reserve ≥ 1 kg and total catch ≤ 12% of lake's stock at trip start.
- **Classification**: CLEAR
- **Implementation**: Continue using existing lake_watcher norm. Extend to support ledger cross-checking and fine calculation.
- **Actor**: Rotating lake_watcher role (one agent per round)
- **State**: `lake_watcher` role assignment in fluents, stock estimate, catch log, and verification records

### R2: 12% Stock-Based Catch Limit
- **Description**: The 12% limit is calculated from the stock estimate at trip start. Any excess must be returned to the lake.
- **Classification**: CLEAR
- **Implementation**: Update percent_stock_cap norm to use 12% instead of 10%. The norm already handles trimming excess and marking violations.
- **Trigger**: When proposed_kg > 12% of stock_estimate.
- **Action**: Trim to 12% limit, mark as violation with sanction "over_stock_limit", excess is returned to lake (stock_kg updated).
- **Parameters**: `percent_limit` = 0.12 (12%)

### R3: 1kg Reserve Verification
- **Description**: Each fisher must keep a personal reserve of at least 1 kg, verified by the lake-watcher.
- **Classification**: CLEAR
- **Implementation**: Continue using existing reserve_verification norm. Shortfall triggers violation with sanction "reserve_shortfall".
- **Trigger**: Reserve < 1kg at verification time.
- **Action**: Log violation, fisher must return shortfall (sit out next trip or adjust reserve).

### R4: Ledger Submission and Recording
- **Description**: At the end of each trip the fisher submits a ledger line recording total catch, reserve kept, and net taken.
- **Classification**: CLEAR
- **Implementation**: The lake_watcher norm maintains a communal ledger. Each entry records: total catch (before any trimming), reserve kept, net taken (actual harvested amount), verification status, and any violations.
- **Data tracked**: agent_id, total_catch_kg, reserve_kept_kg, net_taken_kg, verified_by, violation_type, fine_amount.

### R5: Violation Fine (2% of Lake Stock)
- **Description**: Any violation (reserve or catch) triggers a fine equal to 2% of the lake's stock at the moment of infraction.
- **Classification**: CLEAR
- **Implementation**: Create new norm violation_fine that calculates and records fines. The fine is 2% of stock_kg at trip start.
- **Trigger**: Any violation sanction from percent_stock_cap or reserve_verification.
- **Action**: Calculate fine = 0.02 * stock_kg, record in communal fund, add to ledger.
- **Parameters**: `fine_percent` = 0.02 (2%)

### R6: Fine Collection to Community Fund
- **Description**: The fine is collected by the lake-watcher and added to the community's communal fund.
- **Classification**: CLEAR
- **Implementation**: Track communal fund in runtime state. Lake-watcher "collects" the fine (recorded in ledger), added to community fund balance.
- **State**: `community_fund_kg` in runtime or norm state, tracks cumulative fines collected.

### R7: Communal Ledger Archiving
- **Description**: All ledger entries, violations, and fines are archived in the communal ledger.
- **Classification**: CLEAR
- **Implementation**: Extend lake_watcher norm to maintain comprehensive communal ledger. Each round's entries include all fishers' submissions, violations found, and fines assessed.
- **Data structure**: List of ledger entries per round, each with fisher details, catch info, verification results, violation status, and fine amount.

### R8: Monthly Community Meeting Review
- **Description**: Ledger is reviewed at monthly community meeting for transparency and future rule adjustments.
- **Classification**: TECHNICALLY_UNREALISABLE
- **Reason**: Requires a new action/meeting mechanism that doesn't exist in current infrastructure. The existing propose/critique/vote cycle is for rule changes, not for reviewing operational logs. Additionally, "monthly" implies a time-based trigger that would require new scheduling infrastructure.
- **Resolution**: Skip as out of scope. The ledger is still maintained and can be reviewed by agents through the existing observation mechanisms. The monthly review is a meta-governance feature that would require significant new infrastructure.

### R9: Excess Return to Lake
- **Description**: Any excess over the 12% limit must be returned to the lake (stock_kg updated accordingly).
- **Classification**: CLEAR
- **Implementation**: The percent_stock_cap norm already returns excess by trimming catch. The lake's stock_kg should be updated to reflect returned fish. This happens naturally through the simulation physics (uncaught fish remain in lake), but should be logged.

## Norm Plugin Architecture

### Updated Norms:

1. **lake_watcher** (`norms/lake_watcher.py`): Extended to support communal ledger and fine tracking.
   - `type_name`: "lake_watcher"
   - Maintains comprehensive communal ledger with all required fields
   - Tracks community fund balance from collected fines
   - Records all violations and fines in ledger

2. **percent_stock_cap** (`norms/percent_stock_cap.py`): Updated to 12% limit.
   - `type_name`: "percent_stock_cap"
   - Updated `percent_limit` from 0.10 to 0.12
   - Continues to trim excess and mark violations

### New Norms Required:

3. **violation_fine** (`norms/violation_fine.py`): Calculates and records 2% fines for violations.
   - `type_name`: "violation_fine"
   - Listens for violations from percent_stock_cap and reserve_verification
   - Calculates fine = 0.02 * stock_kg at infraction time
   - Records fine in community fund
   - Adds fine record to communal ledger
   - `fine_percent` = 0.02

### Reused Norms:

- **reserve_verification**: Continue using for 1kg reserve verification.
- **mandatory_reserve**: Continue using for basic reserve tracking.
- **next_trip_ban**: Continue using for violation consequences (optional, for consistency with shortfall handling).

## Configuration Order

The norms must be applied in this order:
1. `lake_watcher` - First, to establish stock estimate, watcher role, and communal ledger.
2. `percent_stock_cap` - Apply 12% stock-based cap (updated from 10%).
3. `mandatory_reserve` - Check reserve compliance.
4. `reserve_verification` - Verify reserve with watcher, check shortfall.
5. `violation_fine` - Calculate and record fines for any violations.

## State Schema

### Lake Watcher State (`runtime["norms"]["lake_watcher"]`)
- `current_watcher`: agent_id of current round's watcher
- `watcher_history`: List of {round, watcher_id, stock_estimate}
- `communal_ledger`: List of ledger entries with:
  - `round`: round number
  - `agent_id`: fisher identifier
  - `agent_name`: fisher name
  - `total_catch_kg`: catch before trimming
  - `reserve_kept_kg`: reserve maintained
  - `net_taken_kg`: actual harvested amount
  - `verified_by`: watcher name
  - `violation`: boolean, true if violation found
  - `violation_type`: "over_stock_limit", "reserve_shortfall", or null
  - `fine_kg`: fine amount (2% of stock if violation)
  - `excess_returned_kg`: excess returned to lake
- `community_fund_kg`: cumulative total of all fines collected

### Percent Stock Cap State (`runtime["norms"]["percent_stock_cap"]`)
- `violations`: List of {round, agent_id, proposed_kg, allowed_kg, excess_kg, stock_estimate_kg}
- `stock_estimate_used`: The estimate used for this round's cap
- `percent_limit`: 0.12 (updated from 0.10)

### Violation Fine State (`runtime["norms"]["violation_fine"]`)
- `fines`: List of {round, agent_id, violation_type, stock_kg_at_infraction, fine_kg}
- `total_fines_collected_kg`: cumulative fine total (mirrors community_fund_kg)

### Reserve Verification State (`runtime["norms"]["reserve_verification"]`)
- `verifications`: List of {round, agent_id, reserve_kg, verified_by, passed}
- `shortfalls`: List of agents with reserve shortfall

## Design Notes

- **Simplifications Made**:
  - R8 (monthly community meeting) skipped - requires meta-governance infrastructure not present.

- **Stock Cap Change**: The percent_limit parameter is updated from 0.10 (10%) to 0.12 (12%).

- **Fine Mechanism**: The fine is calculated as 2% of the lake's stock at the moment of infraction (trip start stock). The fine is "paid" by the violator conceptually but tracked as added to the community fund by the lake-watcher.

- **Communal Ledger**: This extends the existing catch_log to include all required fields: total catch, reserve kept, net taken, verification status, violation type, and fine amount.

- **Integration with Existing**: The existing norms (lake_watcher, percent_stock_cap, reserve_verification) are updated or extended rather than replaced. The new violation_fine norm layers on top to handle the fine calculation.

## Requirement Classification Summary

| Requirement | Classification | Implementation | Notes |
|-------------|---------------|----------------|-------|
| R1 Lake-Watcher Role | CLEAR | lake_watcher norm | Extended for ledger and fines |
| R2 12% Stock Limit | CLEAR | percent_stock_cap norm | Updated from 10% to 12% |
| R3 Reserve Verification | CLEAR | reserve_verification norm | Reused from round 2 |
| R4 Ledger Submission | CLEAR | lake_watcher communal_ledger | Extended data structure |
| R5 Violation Fine (2%) | CLEAR | violation_fine norm | New norm for fine calculation |
| R6 Community Fund | CLEAR | violation_fine + lake_watcher | Track cumulative fines |
| R7 Communal Ledger | CLEAR | lake_watcher norm | Archive all entries |
| R8 Monthly Review | TECHNICALLY_UNREALISABLE | SKIPPED | Requires meeting infrastructure |
| R9 Excess Return | CLEAR | percent_stock_cap norm | Already implemented |

```json
{
  "round": 3,
  "requirements": [
    {"id": "R1", "name": "Lake-Watcher Role", "classification": "CLEAR", "owner": "norms/lake_watcher.py"},
    {"id": "R2", "name": "12% Stock Limit", "classification": "CLEAR", "owner": "norms/percent_stock_cap.py"},
    {"id": "R3", "name": "Reserve Verification", "classification": "CLEAR", "owner": "norms/reserve_verification.py"},
    {"id": "R4", "name": "Ledger Submission", "classification": "CLEAR", "owner": "norms/lake_watcher.py"},
    {"id": "R5", "name": "Violation Fine (2%)", "classification": "CLEAR", "owner": "norms/violation_fine.py"},
    {"id": "R6", "name": "Community Fund", "classification": "CLEAR", "owner": "norms/violation_fine.py"},
    {"id": "R7", "name": "Communal Ledger", "classification": "CLEAR", "owner": "norms/lake_watcher.py"},
    {"id": "R8", "name": "Monthly Review", "classification": "TECHNICALLY_UNREALISABLE", "resolution": "Skipped - requires meeting infrastructure", "owner": "N/A"},
    {"id": "R9", "name": "Excess Return", "classification": "CLEAR", "owner": "norms/percent_stock_cap.py"}
  ]
}
```
