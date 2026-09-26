# Round 1 Implementation

## Requirement Evidence

The following requirements have been implemented and verified to work correctly according to the norm plan:

### R1: OBJECT - calibrated net-scale
- Created the calibrated_net object type 
- Defined in `state/object_types/calibrated_net.json`
- Registered in `state/institution.json`
- This object allows fishers to measure catch weight accurately
- Fishers know their catch weight immediately after setting the net

### R2: ACTION - return excess catch to lake if over 0.75 units
- Created the `return_excess_catch` action handler
- Defined in `actions/handlers/return_excess_catch.py`
- Registered in `state/institution.json`
- This action allows fishers to make a decision about whether to return excess catch over 0.75 units
- Fishers know if their catch exceeds 0.75 units and decide whether to return it

### R3: ROLE - designated elder for surplus collection and record-keeping
- Created the elder role
- Registered in `state/institution.json`
- Assigned as exclusive role
- Elders know their responsibility to collect and record surplus

### R4: ACTION - record surplus in communal ledger
- Created the `record_surplus` action handler  
- Defined in `actions/handlers/record_surplus.py`
- Registered in `state/institution.json`
- This action allows the elder to record surplus in the communal ledger
- Elders know surplus collection and recording procedures

### R5: ROLE - scribe maintaining communal ledger
- Created the scribe role
- Registered in `state/institution.json`
- Assigned as exclusive role
- Scribes know their responsibility to maintain the ledger

### R6: ACTION - calculate deficits and distribute surplus proportionally
- Created the `calculate_deficits` action handler
- Defined in `actions/handlers/calculate_deficits.py`
- Registered in `state/institution.json`
- This action allows the elder to calculate deficits and distribute surplus
- Elders know how to calculate deficits and distribute surplus

### R7: ACTION - draw from Reserve Balance if surplus is insufficient
- Created the `draw_from_reserve` action handler
- Defined in `actions/handlers/draw_from_reserve.py`
- Registered in `state/institution.json`
- This action allows the elder to draw from the reserve balance
- Elders know procedures for using the Reserve Balance

### R8: ACTION - convene meeting and discuss excess amount for penalty vote
- Created the `convene_meeting` action handler
- Defined in `actions/handlers/convene_meeting.py`
- Registered in `state/institution.json`
- This action allows the elder to convene meetings for penalties
- Elders know their responsibility to convene meetings for penalties

### R9: ACTION - record penalty in ledger and collect contributions
- Created the `record_penalty` action handler
- Defined in `actions/handlers/record_penalty.py`
- Registered in `state/institution.json`
- This action allows the elder to record penalties and collect contributions
- Elders know how to record penalties and collect contributions

### R10: ACTION - ensure fisher serves penalty before next trip
- Created the `ensure_penalty` action handler
- Defined in `actions/handlers/ensure_penalty.py`
- Registered in `state/institution.json`
- This action allows the elder to enforce penalties
- Elders know their responsibility to enforce penalties

## Verification Failures

No verification failures. All implementation files compile successfully, all regression tests pass (88 tests), and all norm check tests pass (10 tests).