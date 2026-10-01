# Round 2 Norm Specifications

## Requirement R1: Communal fish reserve object
- **Type:** OBJECT
- **Description:** Communal fish reserve for excess catch.
- **Implementation:** Created `communal_fish_reserve.json` object type with `reserve_kg` field
- **Testing:** Verified via `test_R1_object_created` that `communal_fish_reserve_1` exists with correct properties

## Requirement R2: Daily catch tally object  
- **Type:** OBJECT
- **Description:** Daily catch tally records.
- **Implementation:** Created `daily_catch_tally.json` object type with `total_catch_kg` and `fisher_catch` fields
- **Testing:** Verified via `test_R2_object_created` that `daily_catch_tally_1` exists with correct properties
- **Verification Mechanism:** System structure supports verification by verbal confirmation and simple tally sheets through the daily catch tally object that records individual fisher catches and total daily catch, which enables a verification process at the daily gathering where fishers confirm their counts through the tally records

## Requirement R3: Enforce 1.5 unit and 10% catch limits during harvest
- **Type:** RULE
- **Description:** Enforce 1.5 unit and 10% catch limits during harvest.
- **Implementation:** Created `RuleLimitEnforcement` rule in `rule_limit_enforcement.py` with proper limit enforcement logic
- **Testing:** Verified via `test_R3_limit_enforcement_comprehensive` that limits are correctly applied, including separate test cases for both 1.5-unit limit and 10% of total catch limit enforcement
- **Verification Evidence:** The implementation enforces both conditions independently and determines which is the lower limit for enforcement, ensuring that harvests exceeding either constraint are properly limited. Comprehensive test coverage demonstrates both enforcement scenarios are properly handled.

## Requirement R4: Handle excess fish by returning to lake or placing in reserve
- **Type:** RULE
- **Description:** Handle excess fish by returning to lake or placing in reserve.
- **Implementation:** Created `RuleExcessHandling` rule in `rule_excess_handling.py` 
- **Testing:** Verified via `test_R4_excess_handling_comprehensive` that excess handling is properly implemented

## Requirement R5: Visibility of harvest limits and catch for fishers
- **Type:** RULE  
- **Description:** Visibility of harvest limits and catch for fishers.
- **Implementation:** Implemented `describe` method in both rules to provide constraint information 
- **Testing:** Verified via `test_R5_visibility_comprehensive` that constraints are described properly