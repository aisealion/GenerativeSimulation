# Round 4 Institutional Design Specification

## Policy Summary
No fisher may take more than 4 kg per trip, must keep 1 kg for personal sustenance; surplus is deposited into a communal reserve capped at 70 kg, which is automatically released to raise the lake to 190 kg when its mass falls below 140 kg.

## Requirements Analysis

### R1: 4kg Per-Trip Catch Limit
- **Description**: Every fisher may keep a maximum of 4 kg per trip.
- **Classification**: CLEAR
- **Implementation**: Update catch_cap norm to use 4kg limit instead of 5kg. Violations trigger deposit requirement.
- **Trigger**: When proposed_kg > 4kg.
- **Action**: Trim to 4kg limit, mark as violation with sanction "over_cap".
- **Parameters**: `limit_kg` = 4.0

### R2: 1kg Personal Reserve
- **Description**: Each fisher must keep 1 kg for personal sustenance.
- **Classification**: CLEAR
- **Implementation**: Continue using mandatory_reserve norm with 1kg reserve requirement.
- **Trigger**: Reserve verification at trip start.
- **Action**: Fisher must maintain at least 1kg reserve.
- **Parameters**: `reserve_kg` = 1.0

### R3: Communal Reserve with 70kg Cap
- **Description**: Surplus over 4kg must be deposited into communal reserve held by Kai (lake-watcher), capped at 70 kg.
- **Classification**: CLEAR
- **Implementation**: Create new communal_reserve norm that tracks deposits and manages the reserve balance. Integrates with lake_watcher for Kai's role.
- **Trigger**: When catch exceeds 4kg (from catch_cap violation).
- **Action**: Calculate surplus = catch - 4kg, deposit surplus into communal reserve (up to 70kg cap), excess above cap stays with fisher or is returned to lake.
- **State**: `communal_reserve_kg` tracks current reserve balance, capped at 70kg.

### R4: Ledger Entry with Deposit Status
- **Description**: After each trip, fisher logs: name, trip date, catch amount, deposit status (yes/no). Kai records deposit amount if applicable.
- **Classification**: CLEAR
- **Implementation**: Extend lake_watcher norm to track deposit status and amounts in the communal ledger.
- **Data tracked**: agent_id, round, catch_kg, deposit_kg, deposit_status, personal_reserve_kept.

### R5: Lake Mass Monitoring (Threshold Check)
- **Description**: The community measures lake's mass at trip start. If lake < 140kg, trigger reserve release.
- **Classification**: CLEAR
- **Implementation**: Extend communal_reserve norm to check lake mass at on_round_start. If below threshold, calculate release amount.
- **Trigger**: stock_kg < 140kg at round start.
- **Action**: Calculate required = 190kg - current_mass, release = min(required, reserve_balance).

### R6: Proportional Reserve Release
- **Description**: Using previous round's total catch, compute each fisher's share: share_i = catch_i / totalCatch. Release_i = share_i * release_amount. Add to each fisher's credit balance.
- **Classification**: CLEAR
- **Implementation**: Extend communal_reserve norm to calculate proportional shares based on previous round's catch distribution.
- **Calculation**: proportional share based on contribution to last round's harvest.
- **Action**: Distribute released amount proportionally, deduct from reserve, record in fisher credit balances.

### R7: Release Termination Condition
- **Description**: Stop releasing once lake reaches 190kg or reserve is exhausted.
- **Classification**: CLEAR
- **Implementation**: Built into release calculation in communal_reserve norm.
- **Condition**: Release stops when stock_kg >= 190kg or reserve_balance = 0.

### R8: Violation Detection (Catch > 4kg Without Deposit)
- **Description**: Any ledger entry showing catch > 4kg without corresponding deposit triggers violation flag.
- **Classification**: CLEAR
- **Implementation**: The catch_cap norm already marks over-limit catches as violations. The surplus handling in communal_reserve ensures deposit.
- **Integration**: Violation is implicit if fisher tries to keep > 4kg without depositing surplus.

### R9: Violation Recording
- **Description**: Kai logs violations in the shared ledger.
- **Classification**: CLEAR
- **Implementation**: Extend lake_watcher norm to record violation entries in communal_ledger with violation flag.
- **Data**: round, agent_id, violation_type, expected_deposit_kg, actual_deposit_kg.

### R10: Revocation Process (Council Vote)
- **Description**: Next day, community council (9 other fishers + Kai) reviews violations. Simple majority revokes fishing rights for following month.
- **Classification**: TECHNICALLY_UNREALISABLE
- **Reason**: Requires a new action/meeting mechanism for council voting that doesn't exist. Also requires "next day" and "following month" time concepts not present in the round-based architecture.
- **Resolution**: Skip as out of scope. The violation detection and recording still function; the revocation mechanism would require significant new governance infrastructure.

### R11: Revocation Flag
- **Description**: Ledger records "revoked" flag, fisher cannot log trip until new vote.
- **Classification**: TECHNICALLY_UNREALISABLE
- **Reason**: Depends on R10 (revocation process) which is unrealisable. Also requires persistent ban mechanism across multiple rounds with appeal process.
- **Resolution**: Skip as dependent on unrealisable R10.

### R12: Appeal Process
- **Description**: Revoked fisher may appeal at next monthly meeting; council can overturn with simple majority.
- **Classification**: TECHNICALLY_UNREALISABLE
- **Reason**: Depends on R10 and R11. Requires meeting infrastructure and appeal mechanism not present.
- **Resolution**: Skip as dependent on unrealisable requirements.

### R13: Transparency
- **Description**: All ledger entries, reserve balances, and voting results recorded.
- **Classification**: CLEAR (Partial)
- **Implementation**: Ledger entries and reserve balances are tracked in lake_watcher and communal_reserve norms. Voting results skipped (dependent on unrealisable R10-R12).
- **Data**: Full communal ledger with deposits, releases, violations, reserve balance history.

## Norm Plugin Architecture

### Updated Norms:

1. **catch_cap** (`norms/catch_cap.py`): Updated to 4kg limit.
   - `type_name`: "catch_cap"
   - Updated `limit_kg` from 5.0 to 4.0
   - Violation sanction: "over_cap"

2. **lake_watcher** (`norms/lake_watcher.py`): Extended for deposit tracking and reserve management.
   - `type_name`: "lake_watcher"
   - Tracks Kai's role as reserve holder
   - Records deposit entries in communal ledger
   - Records violation entries
   - Maintains deposit history

### New Norms Required:

3. **communal_reserve** (`norms/communal_reserve.py`): Manages communal reserve with 70kg cap and automatic release.
   - `type_name`: "communal_reserve"
   - Listens for catch_cap violations (catch > 4kg)
   - Calculates surplus to deposit: surplus = catch - 4kg
   - Manages reserve balance with 70kg cap
   - Monitors lake mass at round start
   - Triggers release when stock < 140kg
   - Calculates proportional distribution based on previous round's catch
   - Releases to lake (updates stock_override)
   - Records all transactions: deposits, releases, distributions
   - `max_reserve_kg` = 70.0
   - `release_threshold_kg` = 140.0
   - `release_target_kg` = 190.0

### Reused Norms:

- **mandatory_reserve**: Continue using for 1kg personal reserve requirement.

## Configuration Order

The norms must be applied in this order:
1. `lake_watcher` - Establish Kai's role and communal ledger.
2. `catch_cap` - Apply 4kg catch limit (updated from 5kg).
3. `mandatory_reserve` - Check 1kg personal reserve.
4. `communal_reserve` - Handle surplus deposit, monitor lake mass, trigger releases.

## State Schema

### Lake Watcher State (`runtime["norms"]["lake_watcher"]`)
- `current_watcher`: agent_id of current round's watcher (Kai)
- `communal_ledger`: List of ledger entries with:
  - `round`: round number
  - `agent_id`: fisher identifier
  - `agent_name`: fisher name
  - `catch_kg`: amount caught
  - `deposit_kg`: amount deposited to reserve
  - `deposit_status`: boolean
  - `personal_reserve_kept`: boolean
  - `violation`: boolean
  - `violation_type`: "over_cap_without_deposit" or null
  - `recorded_by`: watcher name (Kai)
- `deposit_history`: List of deposit records

### Catch Cap State (`runtime["norms"]["catch_cap"]`)
- `violations`: List of {round, agent_id, attempted_kg, allowed_kg, excess_kg}
- `limit_kg`: 4.0 (updated from 5.0)

### Communal Reserve State (`runtime["norms"]["communal_reserve"]`)
- `reserve_balance_kg`: current communal reserve amount (capped at 70kg)
- `max_reserve_kg`: 70.0
- `release_threshold_kg`: 140.0
- `release_target_kg`: 190.0
- `deposits`: List of {round, agent_id, catch_kg, deposit_kg, reserve_after_kg}
- `releases`: List of {round, stock_before_kg, required_kg, released_kg, reserve_after_kg}
- `distributions`: List of {round, agent_id, share_ratio, distribution_kg}
- `previous_round_catches`: {agent_id: catch_kg} for proportional calculation
- `previous_round_total`: total catch for proportional calculation

### Mandatory Reserve State (`runtime["norms"]["mandatory_reserve"]`)
- `reserve_kg`: 1.0
- Per-agent reserve tracking (unchanged)

## Design Notes

- **Simplifications Made**:
  - R10-R12 (revocation process, revocation flag, appeal) skipped - requires governance/meeting infrastructure not present.

- **Monthly Concepts**: The policy mentions "monthly" measurements and meetings. The simulation uses a round-based model without explicit months. Interpreted as:
  - "Monthly lake measurement" → Each round's lake mass check
  - "Following month" revocation → Not implemented (R10-R12 skipped)

- **Reserve Release Timing**: Release happens at round start (on_round_start) when lake is below threshold, before fishing begins.

- **Proportional Distribution**: Uses previous round's catch distribution as the basis for shares. This is a reasonable interpretation since the simulation doesn't have explicit "months" of aggregated data.

- **Deposit Handling**: When a fisher catches > 4kg, the excess is automatically deposited. If the reserve is at cap, the excess that can't be deposited is effectively returned (fisher keeps 4kg, rest stays in lake through physics).

- **Integration with Existing**: The existing catch_cap norm is updated (parameter change). The new communal_reserve norm layers on top to handle the surplus deposit and release mechanics.

## Requirement Classification Summary

| Requirement | Classification | Implementation | Notes |
|-------------|---------------|----------------|-------|
| R1 4kg Catch Limit | CLEAR | catch_cap norm | Updated from 5kg to 4kg |
| R2 1kg Personal Reserve | CLEAR | mandatory_reserve norm | Reused |
| R3 Communal Reserve (70kg cap) | CLEAR | communal_reserve norm | New norm for reserve management |
| R4 Ledger Entry | CLEAR | lake_watcher norm | Extended for deposits |
| R5 Lake Mass Monitoring | CLEAR | communal_reserve norm | Threshold check at round start |
| R6 Proportional Release | CLEAR | communal_reserve norm | Distribution based on prior round |
| R7 Release Termination | CLEAR | communal_reserve norm | Built into release calculation |
| R8 Violation Detection | CLEAR | catch_cap + communal_reserve | Violation if no deposit |
| R9 Violation Recording | CLEAR | lake_watcher norm | Ledger entries with violation flag |
| R10 Revocation Process | TECHNICALLY_UNREALISABLE | SKIPPED | Requires meeting infrastructure |
| R11 Revocation Flag | TECHNICALLY_UNREALISABLE | SKIPPED | Depends on R10 |
| R12 Appeal Process | TECHNICALLY_UNREALISABLE | SKIPPED | Depends on R10-R11 |
| R13 Transparency | CLEAR (Partial) | lake_watcher + communal_reserve | Voting results skipped |

```json
{
  "round": 4,
  "requirements": [
    {"id": "R1", "name": "4kg Catch Limit", "classification": "CLEAR", "owner": "norms/catch_cap.py"},
    {"id": "R2", "name": "1kg Personal Reserve", "classification": "CLEAR", "owner": "norms/mandatory_reserve.py"},
    {"id": "R3", "name": "Communal Reserve (70kg cap)", "classification": "CLEAR", "owner": "norms/communal_reserve.py"},
    {"id": "R4", "name": "Ledger Entry", "classification": "CLEAR", "owner": "norms/lake_watcher.py"},
    {"id": "R5", "name": "Lake Mass Monitoring", "classification": "CLEAR", "owner": "norms/communal_reserve.py"},
    {"id": "R6", "name": "Proportional Release", "classification": "CLEAR", "owner": "norms/communal_reserve.py"},
    {"id": "R7", "name": "Release Termination", "classification": "CLEAR", "owner": "norms/communal_reserve.py"},
    {"id": "R8", "name": "Violation Detection", "classification": "CLEAR", "owner": "norms/catch_cap.py + norms/communal_reserve.py"},
    {"id": "R9", "name": "Violation Recording", "classification": "CLEAR", "owner": "norms/lake_watcher.py"},
    {"id": "R10", "name": "Revocation Process", "classification": "TECHNICALLY_UNREALISABLE", "resolution": "Skipped - requires meeting infrastructure", "owner": "N/A"},
    {"id": "R11", "name": "Revocation Flag", "classification": "TECHNICALLY_UNREALISABLE", "resolution": "Skipped - depends on R10", "owner": "N/A"},
    {"id": "R12", "name": "Appeal Process", "classification": "TECHNICALLY_UNREALISABLE", "resolution": "Skipped - depends on R10-R11", "owner": "N/A"},
    {"id": "R13", "name": "Transparency", "classification": "CLEAR", "owner": "norms/lake_watcher.py + norms/communal_reserve.py"}
  ]
}
```
