# Round 2 Norm Specifications

## Requirement R1
### Role: observer exists
**Agent Experience:** The observer role is registered and exists in the institution.

**Implementation:** 
- Observer role is defined in state/institution.json with exclusive=True and introduced in round 2
- Defined in roles.roles.assign_role()  
- Observer has lifecycle attributes (duration_rounds=1, renewable=True)

### Test
`test_R1_observer_role_exists` - Confirms observer role registration

## Requirement R2
### Role: fisher catch recording 
**Agent Experience:** Fisher can record catch through the record_catch action.

**Implementation:**
- Fishers can initiate "record_catch" action 
- Action requires actor "fisher"  
- Action triggers catch recording behavior

### Test  
`test_R2_fisher_catch_recording` - Confirms fisher can record catch

## Requirement R3
### Object: personal ledger
**Agent Experience:** Fisher has access to a personal ledger object with unique tracking.

**Implementation:**
- "personal_ledger" object type defined in state/institution.json
- Object properties defined in state/object_types/personal_ledger.json
- Personal ledger tracks fisher's individual catch records

### Test
`test_R3_personal_ledger_object` - Confirms personal ledger object exists

## Requirement R4  
### Role: fisher report catch
**Agent Experience:** Fisher reports catch to community observer.

**Implementation:**
- Fisher initiates report_catch action
- Action requires fisher as actor  
- Reports catch to observer

### Test
`test_R4_fisher_report_catch` - Confirms fisher reporting

## Requirement R5
### Role: observer update ledger
**Agent Experience:** Observer updates communal ledger with catch records.

**Implementation:**
- Observer role updates communal ledger in record_catch action
- Updates ledger with catch information
- Ledger records all fisher catches

### Test
`test_R5_observer_update_ledger` - Confirms observer ledger updates

## Requirement R6
### Object: communal ledger  
**Agent Experience:** Community has collective ledger tracking all catches.

**Implementation:**
- "communal_ledger" object type defined in state/institution.json
- Object properties defined in state/object_types/communal_ledger.json
- Ledger tracks community-wide catches

### Test
`test_R6_communal_ledger_object` - Confirms communal ledger exists

## Requirement R7
### Role: observer mark reserved units
**Agent Experience:** Observer can mark reserved catch units.

**Implementation:**
- Observer role can initiate mark_reserved action
- Marks reserved fish units in state
- Ensures proper allocation tracking

### Test  
`test_R7_observer_marks_reserved` - Confirms observer can mark reserved

## Requirement R8
### Object: reserved units
**Agent Experience:** Community maintains a reserve of fish units.

**Implementation:**
- "reserved_units" object type defined in state/institution.json  
- Object properties defined in state/object_types/reserved_units.json
- Tracks reserve units for community use

### Test
`test_R8_reserved_units_object` - Confirms reserved units object

## Requirement R9
### Role: lake keeper record stock
**Agent Experience:** Lake keeper records current lake stock.

**Implementation:**
- Lake keeper role can initiate record_stock action
- Records current fish stock levels
- Checks lake stock before trips

### Test
`test_R9_lake_keeper_records_stock` - Confirms lake keeper stock records

## Requirement R10
### Rule: pre-trip check
**Agent Experience:** Lake keeper checks that stock ≥ 1 unit before fishing trips.

**Implementation:**  
- Pre-trip_check rule applied to harvest action
- Blocks fishing if lake holds < 1 unit
- Uses rule type "pre_trip_check" 

### Test
`test_R10_pre_trip_check_rule` - Confirms pre-trip check works

## Requirement R11
### Rule: max catch limit
**Agent Experience:** Fishers limited to 3 units maximum per fishing trip.

**Implementation:
- Max_catch_limit rule applied to harvest action
- Prevents fishing beyond 3 units
- Uses rule type "max_catch_limit"

### Test  
`test_R11_max_catch_limit_rule` - Confirms catch limit enforced

## Requirement R12
### Rule: min stock requirement  
**Agent Experience:** Lake must hold at least one unit after each trip.

**Implementation:**
- Min_stock_requirement rule applied to harvest action
- Enforces minimum stock after each fisher trip  
- Uses rule type "min_stock_requirement" 

### Test
`test_R12_min_stock_requirement_rule` - Confirms minimum stock rule

## Requirement R13
### Action: observer confirms stock
**Agent Experience:** Observer confirms lake has ≥1 unit stock before fishing trip.

**Implementation:**
- Action "confirm_stock" defined in state/actions/confirm_stock.json  
- Requires actor "observer"
- Checks and confirms stock level
- Execution uses handler "generic_agent_decision"

### Test
`test_R13_observer_confirms_stock` - Confirms observer stock confirmation  

## Requirement R14
### Action: trip denied if stock low
**Agent Experience:** Fishing trip denied when lake holds < 1 unit.

**Implementation: 
- Pre-trip check rule blocks participation
- Action is denied automatically when stock < 1
- Uses pre_trip_check rule

### Test
`test_R14_trip_denied_if_stock_low` - Confirms trips denied when stock low

## Requirement R15
### Action: fisher returns excess
**Agent Experience:** Fishers return excess catch to the lake immediately.

**Implementation:
- Action "return_excess" defined in state/actions/return_excess.json 
- Requires actor "fisher"
- Ensures surplus fish returned
- Execution uses handler "generic_agent_decision"

### Test
`test_R15_fisher_returns_excess` - Confirms fisher returns excess

## Requirement R16
### Action: observer flags violations  
**Agent Experience:** Observer flags fishers who exceed limits.

**Implementation:
- Action "flag_violation" defined in state/actions/flag_violation.json
- Requires actor "observer"  
- Tracks violation flags
- Execution uses handler "generic_agent_decision"

### Test
`test_R16_observer_flags_violations` - Confirms observer flags violations

## Requirement R17
### Rule: skip day
**Agent Experience:** Repeated violations trigger skip day enforcement.

**Implementation:
- Violation_skip_day rule applies to harvest action
- Two consecutive or three separate violations/month trigger skip
- Uses rule type "violation_skip_day"

### Test  
`test_R17_skip_day_rule` - Confirms skip day rule works

## Requirement R18
### Role: elders impose skip day  
**Agent Experience:** Fishing elders enforce skip day sanctions.

**Implementation:
- Elders role has decision-making authority  
- Applies skip day sanctions
- Uses violation_skip_day rule

### Test
`test_R18_elders_impose_skip_day` - Confirms elders can impose skip day

## Requirement R19
### Rule: annual fine
**Agent Experience:** Community council sets annual fine for repeated violations.

**Implementation:
- Annual_fine rule applies to fisher payoff adjustments  
- Uses rule type "annual_fine"
- Council sets fine amount

### Test
`test_R19_annual_fine_rule` - Confirms annual fine rule works

## Requirement R20
### Action: lake keeper reviews records
**Agent Experience:** Lake keeper reviews ledger records and catch histories.

**Implementation:
- Action "review_records" defined in state/actions/review_records.json
- Requires actor "lake_keeper"  
- Reviews all ledger entries
- Execution uses handler "generic_agent_decision"

### Test
`test_R20_lake_keeper_reviews_records` - Confirms keeper reviews records

## Requirement R21
### Visibility: ledger records
**Agent Experience:** Ledger records are visible to community.

**Implementation:
- Ledger objects have public visibility
- Community can access all record information
- Ledger entries are transparent

### Test
`test_R21_ledger_visibility` - Confirms ledger visibility

## Requirement R22
### Role: observer rotation
**Agent Experience:** Observer role rotates with defined lifecycle.

**Implementation:
- Observer role set with lifecycle.duration_rounds = 1
- Observer role is renewable
- Role rotates each round

### Test  
`test_R22_observer_role_rotation` - Confirms observer rotation

## Requirement R23
### Role: lake keeper appointment
**Agent Experience:** Lake keeper appointed with defined appointment lifecycle.

**Implementation: 
- Lake keeper role set with duration_rounds = 12
- Lake keeper role is renewable
- Appointment lasts 12 rounds

### Test
`test_R23_lake_keeper_appointment` - Confirms keeper appointment

## Requirement R24
### Rule: violation month cycle
**Agent Experience:** Violation tracking resets monthly.

**Implementation:
- Violation tracking has monthly cycle
- Tally resets over time
- Tracks violations per period

### Test
`test_R24_violation_month_cycle` - Confirms violation cycle