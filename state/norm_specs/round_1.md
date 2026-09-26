# Round 1: Fisheries Management Rules

This round implements the initial fisheries management framework with key roles, objects and rules.

## Roles

- **Trip Leader (R1)**: Elected daily by simple majority vote from among fishers. Measures lake weight immediately after election and calculates catch cap.
- **Pit Steward (R8)**: Elected by unanimous vote from among fishers. Manages the communal fish pit.

## Actions

- **Measure Lake Weight**: Trip leader action to measure lake weight immediately after election.  
- **Catch Submission**: Fishers submit intended catches to trip leader.

## Objects

- **Communal Pit**: For returned fish - persistent communal storage for excess catch.
- **Reserve Fund**: Set at 25% of lake weight - persistent fund for conservation.

## Rules

- **Catch Cap Calculation**: max(0.10 × lake weight, 1.5 kg) for each fisher
- **5% Penalty**: Applied to excess weight paid to reserve fund
- **Monthly Fund Recalculation**: Reserve fund recalculated monthly
- **Exceeding Cap Flagging**: Fishers flagged for consistently exceeding cap
- **24-hour Reporting**: Catch reports must be submitted within 24 hours
- **Monthly Meeting**: Community Council reviews lake health and adjusts cap

All roles, actions and objects are properly defined in the institution specification and functional tests are in place. Note that the actual implementation details for rule enforcement (especially for cap calculation, penalties and tracking) require more elaborate coding than can be demonstrated here.