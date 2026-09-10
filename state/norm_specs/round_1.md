# Round 1 Institutional Design Specification

## Source Norm (from norm.txt)

**Policy:** Each fisher may take no more than 10% of the lake's current total weight per trip, but must keep at least 1 kg for sustenance; any excess must be returned to the lake or a fee equal to the excess weight in fish value must be paid, and the council may adjust the 10% limit only with a majority vote when the lake stock changes dramatically.

**Operationalization:**
1. At the start of each month, the rotating council of five fishers, elected by simple majority, convenes and orders the Stock Watchers to conduct a calibrated trawl‑net survey at representative sites.
2. The survey yields a total fish‑weight estimate, which the council records in the shared logbook as the "current total weight" for that month and posts it in the community folder.
3. Before each trip, a fisher reads that number from the logbook and calculates the allowable catch as 10% of it, with a floor of 1 kg.
4. The fisher records the actual catch weight in the logbook using the shared hand‑held scale, and takes a timestamped photo of the net and weigh‑in.
5. After every trip, a random member of the community spot‑checks the weigh‑in; if the discrepancy exceeds 10%, the case is reviewed.
6. At the monthly council meeting, all entries are reviewed; fishers who exceeded the 10% limit must either return the excess fish to the lake or pay a fee calculated as excess weight × current fish‑value per kg, paid in coin or credit.
7. If the council votes to change the 10% figure, the new figure takes effect at the next meeting.
8. The council may consider adjusting the limit only when a "dramatic" change occurs: a >20% drop in the monthly estimate, a drop below 2,000 kg, or two consecutive months of >10% declines.

---

## Requirement Classification

### R1: Per-Trip Catch Cap (10% of Stock)
- **Description:** Each fisher's catch per trip is capped at 10% of the lake's current total weight (stock_before).
- **Clarity:** CLEAR
- **Implementation:** Norm plugin `catch_cap_10pct` will evaluate each agent's catch and trim to 10% of stock_before if exceeded.
- **Formula:** `limit_kg = stock_before * 0.10`

### R2: Minimum Sustenance Floor (1 kg)
- **Description:** Fishers must keep at least 1 kg for sustenance. This means the effective catch is max(10% of stock, 1 kg) when the 10% calculation yields less than 1 kg.
- **Clarity:** CLEAR (interpreted as: the minimum a fisher can keep is 1 kg; if 10% of stock < 1 kg, they may still keep 1 kg)
- **Implementation:** The norm will apply a floor of 1 kg to the kept amount.
- **Formula:** `kept_kg = min(raw_kg, max(limit_kg, 1.0))`

### R3: Excess Return or Fee Payment
- **Description:** Fishers who exceed the 10% limit must either return excess fish or pay a fee.
- **Clarity:** AMBIGUOUS (operationalization says this happens at monthly council meeting; unclear if this is enforced per-trip or batched)
- **Resolution:** For Round 1, implement per-trip enforcement where excess is automatically forfeited (returned to lake). The fee mechanism requires additional institutional infrastructure (coin/credit system) not yet in place.
- **Implementation:** When catch exceeds 10% limit, the norm reduces kept_kg to the limit and records the violation.

### R4: Monthly Survey and Logbook
- **Description:** Stock Watchers conduct monthly surveys; results recorded as "current total weight".
- **Clarity:** AMBIGUOUS (the simulation already tracks stock_kg; unclear if this requires new actions/roles)
- **Resolution:** The existing `stock_kg` in runtime serves as the logbook's "current total weight". No new survey action needed for Round 1—the stock is already known.

### R5: Council Elections (5 fishers, simple majority)
- **Description:** Rotating council of five fishers elected by simple majority at start of each month.
- **Clarity:** AMBIGUOUS (requires new institutional infrastructure: voting action for council seats, role system)
- **Resolution:** DEFERRED to future round. Round 1 focuses on the core catch constraint.

### R6: Spot-Checks and Discrepancy Review
- **Description:** Random community member spot-checks weigh-in; >10% discrepancy triggers review.
- **Clarity:** AMBIGUOUS (requires random selection mechanism, discrepancy calculation, review process)
- **Resolution:** DEFERRED to future round. The core cap enforcement is deterministic.

### R7: Council Authority to Adjust 10% Limit
- **Description:** Council may vote to change the 10% figure; new figure takes effect next meeting.
- **Clarity:** CLEAR but requires council infrastructure (R5)
- **Resolution:** DEFERRED to future round. The 10% limit is fixed in Round 1.

### R8: Dramatic Change Triggers for Adjustment
- **Description:** Council may consider adjusting limit only when: >20% drop, below 2,000 kg, or two consecutive >10% declines.
- **Clarity:** CLEAR but requires council infrastructure and historical tracking
- **Resolution:** DEFERRED to future round. Round 1 norms do not include adaptive limit adjustment.

---

## Implementation Summary for Round 1

### Scope
Implement the core catch constraint mechanism:
- **Hard cap:** 10% of current stock per trip
- **Sustenance floor:** 1 kg minimum kept (even if 10% of stock < 1 kg)
- **Enforcement:** Automatic reduction of excess catch; violation recorded

### Deferred to Future Rounds
- Council elections and governance structure
- Monthly survey formalization
- Spot-check mechanisms
- Fee payment system (requires currency/credit)
- Adaptive limit adjustment based on stock triggers

### Files to Create/Modify
1. `norms/catch_cap_10pct.py` - New norm plugin implementing R1 and R2
2. `state/config.json` - Add norm configuration
3. `tests/norm_checks/test_round_1_catch_cap.py` - Unit tests

### Fluent/State Changes
None required for Round 1. Uses existing `stock_kg` tracking.

### Config Schema
```json
{
  "norms": [
    {
      "type": "catch_cap_10pct",
      "id": "round1_cap"
    }
  ]
}
```

---

## Verification Criteria

1. When stock is 300 kg, cap is 30 kg per fisher per trip
2. When stock is 5 kg, fisher may still keep 1 kg (floor)
3. When stock is 100 kg, cap is 10 kg
4. Excess catch is trimmed and recorded as violation
5. Violation note includes the amount of excess returned
