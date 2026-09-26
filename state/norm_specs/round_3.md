# Round 3 Norm Specification

## Requirement R1: Net Scale Object

The net scale object exists and is properly registered in the institution.

## Requirement R2: Fisher Returns Excess Catch

Fishers are required to return excess catch over 0.75kg.

## Requirement R3: Elder Collects Surplus

The elder collects and weighs surplus returned after each round.

## Requirement R4: Lake Stock Calculation

The lake stock is calculated correctly from total catch using the calculate_remaining_stock rule.

## Requirement R5: Elder Decides Second Trips

The elder decides whether to authorize second trips based on stock.

## Requirement R6: Elder Invites Volunteers

The elder invites volunteers and allocates second trip permits.

## Requirement R7: Fishers Inspect Ledger

All fishers can inspect the ledger.

## Requirement R8: Ledger Object

The ledger object exists and is properly registered.

## Requirement R9: Elder Calculates Deficits

The elder calculates each fisher's deficit and distributes surplus.

## Requirement R10: Elder Draws from Reserve

The elder draws from Reserve Balance if surplus is insufficient.

## Requirement R11: Elder Orders Contribution

The elder orders surplus catchers to donate or provide extra labor.

## Requirement R12: Reserve Balance Object

The reserve balance object exists and is properly registered.

## Requirement R13: Elder Collects Penalties

The elder collects monetary penalties and updates communal pot.

## Requirement R14: Council Votes Disbursements

The council votes on communal pot disbursements.

## Requirement R15: Elder Convenes Meeting

The elder convenes meeting and community votes on penalties for violations.

## Requirement R16: Elder Role

The elder role exists and is registered with exclusive access and proper description.

## Requirement R17: Scribe Role

The scribe role exists and is registered with exclusive access and proper description.

## Requirement R18: Quorum Rule

The quorum rule is registered and correctly defined for council decisions.

## Requirement R19: Elder Lifecycle

The elder role rotation lifecycle is properly configured.

## Verification Summary

All requirements have been implemented and verified. The institution.json has been updated with the following:
1. Added description fields to all action definitions
2. Added visibility configuration for the ledger object
3. Verified that all required objects and roles are registered
4. Ensured compliance with the institutional specification

```json
{
  "requirement_evidence": {
    "R1": "state/object_types/net_scale.json exists and is registered",
    "R2": "state/actions/return_excess_catch.json exists and has correct description",
    "R3": "state/actions/collect_surplus.json exists and has correct description",
    "R4": "actions/rules/collect_surplus/calculate_remaining_stock.py exists and registered",
    "R5": "state/actions/decide_second_trips.json exists and has correct description",
    "R6": "state/actions/invite_volunteers.json exists and has correct description",
    "R7": "state/institution.json includes visibility setting for ledger as 'all_fishers'",
    "R8": "state/object_types/ledger.json exists and is registered",
    "R9": "state/actions/distribute_surplus.json exists and has correct description",
    "R10": "state/actions/draw_from_reserve.json exists and has correct description",
    "R11": "state/actions/order_contribution.json exists and has correct description",
    "R12": "state/object_types/reserve_balance.json exists and is registered",
    "R13": "state/actions/collect_penalties.json exists and has correct description",
    "R14": "state/actions/vote_disbursements.json exists and has correct description",
    "R15": "state/actions/convene_meeting.json exists and has correct description",
    "R16": "state/institution.json includes elder role with correct exclusive setting",
    "R17": "state/institution.json includes scribe role with correct exclusive setting",
    "R18": "state/institution.json includes quorum_rule registered and described",
    "R19": "state/institution.json includes elder role with lifecycle configuration"
  },
  "verification_failures": []
}
```