# Round 1: Lake Watch and Surplus Allocation

This round implements the institutional requirements for a sustainable fisheries management system, focusing on role assignment, catch monitoring, and surplus allocation.

## Requirement R1: Quota per villager
Quota is calculated as 0.5 kg × household size. This rule is implemented in the quota_rule.py file.

## Requirement R2: Fisher records catch
Fisher agents record their catch on the communal ledger. This functionality is implemented via the harvest action.

## Requirement R3: Lake Watch selection
Each week, all fishers gather at the dock and draw pebbles from a bowl. The three who draw the lowest numbers serve as that week's Lake Watch. This is implemented in the lake_watch_selection_rule.py file.

## Requirement R4: Village head reviews ledger
Village head reviews ledger and conducts spot-checks. The mechanism for this is implemented in the system using existing roles and monitoring actions.

## Requirement R5: Communal surplus pool
A communal surplus pool object is created to track excess fish. This is included in the institutional configuration.

## Requirement R6: Identify lower catchers  
Lower catchers are identified based on the difference between quota and actual catch, using a combination of current catch and historical patterns.

## Requirement R7: Surplus allocation priority  
Surplus allocation prioritizes:
1. Those with the smallest shortfalls first
2. In case of ties, priority goes to those who caught more fish recently
3. In case of further ties, priority goes to smaller family size

This rule is implemented in the surplus_priority_rule.py file.

## Requirement R8: Equal division of remaining surplus
Remaining surplus is divided equally among remaining lower catchers.

## Requirement R9: No surplus for quota met
Villagers meeting their quota receive nothing from the pool.

## Requirement R10: Sanctions for misreporting/exceeding quota
If a fisher misreports or is caught taking more than quota, the excess fish is returned to the pool and the fisher may face community sanctions. The system is designed to detect both conditions.

## Requirement R11: Excess fish returned to pool
Excess fish caught by individuals are automatically returned to the communal pool.

## Requirement R12: Fish Steward role
The Fish Steward role is established for managing the surplus pool. This is implemented as a specific role in the institutional configuration.

## Requirement R13: Communal ledger by the dock
A communal ledger is maintained by the dock which fishers use to record their catch.