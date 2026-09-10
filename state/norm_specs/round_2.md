# Round 2 Institutional Design Specification

## Policy Summary
No fisher may take more than 10% of the lake's current stock per trip and must keep a 1 kg personal reserve for sustenance. Stock estimation happens before each trip by a designated lake-watcher (or consensus if no watcher). The 10% limit is enforced with verification, excess logging, and redistribution. Non-compliance results in sitting out the next trip.

## Requirements Analysis

### R1: Lake-Watcher Role (Stock Estimation)
- **Description**: Before each trip, a designated lake-watcher estimates the lake's current stock via sampling and scaling, or by consensus averaging if no watcher.
- **Classification**: CLEAR
- **Implementation**: A rotating "lake_watcher" role is assigned each round. The watcher "estimates" stock (using the actual physics stock value as their estimate, representing their sampling/scaling). This is implemented as a norm plugin that tracks the current watcher.
- **Actor**: Rotating lake_watcher role (one agent per round)
- **State**: `lake_watcher` role assignment in fluents, stock estimate in norm state
- **Verification**: Check fluents for role assignment, check norm state for estimate record

### R2: 10% Stock-Based Catch Limit
- **Description**: The 10% limit is calculated from the stock estimate.
- **Classification**: CLEAR
- **Implementation**: A norm plugin that caps each fisher's catch at 10% of the estimated stock. The estimate comes from R1's lake-watcher or defaults to actual stock.
- **Trigger**: When proposed_kg > 10% of stock_estimate.
- **Action**: Trim to 10% limit, mark as violation with sanction "over_stock_limit".
- **Parameters**: `percent_limit` = 0.10 (10%)

### R3: Shared Catch Log
- **Description**: Each fisher records the weight of their catch in the shared log.
- **Classification**: CLEAR
- **Implementation**: The lake_watcher norm plugin maintains a ledger of all catches per round.
- **Data tracked**: agent_id, catch_kg, round, verified_by (watcher name), excess_returned.

### R4: Post-Trip Catch Verification
- **Description**: The lake-watcher (or random fisher if no watcher) verifies each catch against the 10% limit immediately after the trip; if exceeded, excess is logged as "Excess returned" and must be returned before next trip.
- **Classification**: CLEAR
- **Implementation**: The 10% cap norm handles verification. Excess is logged in the lake_watcher's ledger. The "must be returned before next trip" is enforced via the violation sanction and note.
- **Trigger**: Catch > 10% of stock estimate.
- **Action**: Log violation, mark excess for return.

### R5: 1kg Reserve Verification
- **Description**: The fisher's 1 kg reserve is weighed by the watcher before departure and logged as "Reserve kept: 1 kg – verified by [watcher]"; any shortfall forces the fisher to sit out the next trip.
- **Classification**: CLEAR
- **Implementation**: Reuse mandatory_reserve norm (already exists) but extend to track verification by lake_watcher. Shortfall triggers eligibility block for next trip via violation_handler integration.
- **Trigger**: Reserve < 1kg at verification time.
- **Action**: Log "Reserve kept: 1kg – verified by [watcher]" or mark violation if shortfall.

### R6: Excess Redistribution by Vote
- **Description**: Excess catch from non-compliant fishers is redistributed by a quick vote of compliant fishers after each trip, giving each an equal share.
- **Classification**: TECHNICALLY_UNREALISABLE
- **Reason**: The simulation does not model a "quick vote" mechanism for redistribution within a single round's harvest action. The existing infrastructure has vote as a separate proposal/critique/vote cycle for rule changes, not for per-trip resource allocation decisions. Implementing a genuine vote-based redistribution would require a new action between harvest rounds, which would significantly complicate the round structure.
- **Resolution**: Implement deterministic redistribution (equal split among compliant fishers) as a simplification. This achieves the same outcome (compliant fishers get equal shares of excess) without the voting infrastructure.

### R7: 3-Month Rule Review (20% Stock Change Trigger)
- **Description**: Every three months the community compares the latest lake estimate to the previous one; a change >20% triggers a rule review, and a simple majority vote decides whether to tighten or relax the 10% limit.
- **Classification**: TECHNICALLY_UNREALISABLE
- **Reason**: Requires (a) a new action for rule review/proposal, and (b) integration with the existing vote infrastructure to modify config at runtime. The existing propose/critique/vote cycle is for adopting new norms, not for adjusting parameters of existing norms mid-simulation. Additionally, "simple majority vote decides" implies a decision mechanism that doesn't exist in the current infrastructure.
- **Resolution**: Skip as out of scope. This is a meta-governance feature that would require significant new infrastructure.

### R8: Non-Compliance Consequences
- **Description**: Non-compliance results in the fisher sitting out the next trip, and their excess fish is given to compliant fishers per the vote.
- **Classification**: CLEAR (with deterministic redistribution instead of vote)
- **Implementation**: Reuse repeated_violation_ban norm pattern - set banned_until_round for next round only. Redistribution of excess to compliant fishers happens via payoff adjustment in on_agent_settled.
- **Trigger**: Violation of 10% limit or reserve shortfall.
- **Action**: Ban for 1 round, redistribute excess equally to compliant fishers.

## Norm Plugin Architecture

### New Norms Required:

1. **lake_watcher** (`norms/lake_watcher.py`): Manages rotating lake-watcher role, stock estimation, and verification logging.
   - `type_name`: "lake_watcher"
   - Tracks current watcher via fluents/role assignment
   - Records stock estimate each round
   - Maintains catch log with verification records

2. **percent_stock_cap** (`norms/percent_stock_cap.py`): Enforces 10% of estimated stock limit.
   - `type_name`: "percent_stock_cap"
   - Reads stock estimate from lake_watcher norm state
   - Caps catch at percent_limit * stock_estimate
   - Sanction: "over_stock_limit"

3. **reserve_verification** (`norms/reserve_verification.py`): Extends reserve checking with watcher verification and shortfall handling.
   - `type_name`: "reserve_verification"
   - Coordinates with lake_watcher for who verifies
   - Shortfall triggers violation and next-round ban

4. **excess_redistribution** (`norms/excess_redistribution.py`): Redistributes excess from violators to compliant fishers.
   - `type_name`: "excess_redistribution"
   - In on_round_end, calculate total excess from violations
   - Split equally among compliant agents, add to their payoff

5. **next_trip_ban** (`norms/next_trip_ban.py`): Implements single-round ban for violations.
   - `type_name`: "next_trip_ban"
   - is_eligible returns False if banned_this_round
   - Triggered by sanctions from percent_stock_cap or reserve_verification

### Reused Norms:

- **mandatory_reserve**: Keep for basic 1kg reserve tracking, but reserve_verification will layer on top.

## Configuration Order

The norms must be applied in this order:
1. `lake_watcher` - First, to establish stock estimate and watcher role.
2. `percent_stock_cap` - Apply 10% stock-based cap.
3. `mandatory_reserve` - Check reserve compliance.
4. `reserve_verification` - Verify reserve with watcher, check shortfall.
5. `next_trip_ban` - Check eligibility based on previous violation.
6. `excess_redistribution` - Final redistribution of excess to compliant fishers.

## State Schema

### Lake Watcher State (`runtime["norms"]["lake_watcher"]`)
- `current_watcher`: agent_id of current round's watcher
- `watcher_history`: List of {round, watcher_id, stock_estimate}
- `catch_log`: List of {round, agent_id, catch_kg, verified_by, excess_kg}

### Percent Stock Cap State (`runtime["norms"]["percent_stock_cap"]`)
- `violations`: List of {round, agent_id, proposed_kg, allowed_kg, excess_kg}
- `stock_estimate_used`: The estimate used for this round's cap

### Reserve Verification State (`runtime["norms"]["reserve_verification"]`)
- `verifications`: List of {round, agent_id, reserve_kg, verified_by, passed}
- `shortfalls`: List of agents with reserve shortfall (triggers next_trip_ban)

### Next Trip Ban State (`runtime["norms"]["next_trip_ban"]`)
- `banned_agents`: Dict of agent_id -> banned_until_round
- `ban_reasons`: Dict of agent_id -> {round, reason}

### Excess Redistribution State (`runtime["norms"]["excess_redistribution"]`)
- `redistributions`: List of {round, total_excess_kg, compliant_count, share_per_agent}
- `agent_receipts`: Dict of agent_id -> total_redistributed_kg

## Design Notes

- **Simplifications Made**:
  - R6 (vote-based redistribution) simplified to deterministic equal split - achieves same outcome without voting infrastructure.
  - R7 (3-month rule review) skipped - requires meta-governance infrastructure not present.

- **Role Rotation**: The lake_watcher role rotates each round among alive fishers. Implemented via on_round_end selecting next watcher and assign_role.

- **Stock Estimation**: The lake-watcher "estimates" by using the actual physics stock value, which represents their professional sampling/scaling ability.

- **Integration with Existing**: The mandatory_reserve norm is kept but extended - the reserve_verification norm adds the watcher verification layer and shortfall consequence.

## Requirement Classification Summary

| Requirement | Classification | Implementation | Notes |
|-------------|---------------|----------------|-------|
| R1 Lake-Watcher | CLEAR | lake_watcher norm | Rotating role, stock estimate |
| R2 10% Stock Limit | CLEAR | percent_stock_cap norm | Dynamic cap based on estimate |
| R3 Shared Log | CLEAR | lake_watcher ledger | Catch recording with verification |
| R4 Verification | CLEAR | percent_stock_cap + lake_watcher | Post-trip verification logging |
| R5 Reserve Verification | CLEAR | reserve_verification norm | Watcher-verified reserve check |
| R6 Redistribution | TECHNICALLY_UNREALISABLE | excess_redistribution norm | Deterministic instead of vote |
| R7 Rule Review | TECHNICALLY_UNREALISABLE | SKIPPED | Requires meta-governance infra |
| R8 Non-Compliance | CLEAR | next_trip_ban norm | 1-round ban, excess redistribution |

```json
{
  "round": 2,
  "requirements": [
    {"id": "R1", "name": "Lake-Watcher Role", "classification": "CLEAR", "owner": "norms/lake_watcher.py"},
    {"id": "R2", "name": "10% Stock Limit", "classification": "CLEAR", "owner": "norms/percent_stock_cap.py"},
    {"id": "R3", "name": "Shared Catch Log", "classification": "CLEAR", "owner": "norms/lake_watcher.py"},
    {"id": "R4", "name": "Post-Trip Verification", "classification": "CLEAR", "owner": "norms/percent_stock_cap.py"},
    {"id": "R5", "name": "Reserve Verification", "classification": "CLEAR", "owner": "norms/reserve_verification.py"},
    {"id": "R6", "name": "Excess Redistribution", "classification": "TECHNICALLY_UNREALISABLE", "resolution": "Deterministic equal split instead of vote", "owner": "norms/excess_redistribution.py"},
    {"id": "R7", "name": "3-Month Rule Review", "classification": "TECHNICALLY_UNREALISABLE", "resolution": "Skipped - requires meta-governance", "owner": "N/A"},
    {"id": "R8", "name": "Non-Compliance Consequences", "classification": "CLEAR", "owner": "norms/next_trip_ban.py"}
  ]
}
```
