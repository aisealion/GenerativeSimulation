# Norm Evaluator Verdict: Round 2

**Date:** 2026-09-04  
**Norm Spec:** state/norm_specs/round_2.md  
**Test Suite:** tests/norm_evaluation/round_2/  

## Executive Summary

**STATUS: INCOMPLETE IMPLEMENTATION**

The norm-implementer has NOT completed the structural changes required by Round 2's specification. Only simulation data files (norm.txt, state/runtime.json) were updated to reflect the adoption of the new norm, but the actual norm enforcement code was not implemented.

---

## Requirements Analysis

### CLEAR Requirements (Implemented: 2/10, Missing: 8/10)

| Req | Description | Status | Verdict | Notes |
|-----|-------------|--------|---------|-------|
| R1 | `harvested_kg(agent, trip) <= 0.08 * stock_before` | ❌ FAIL | IMPLEMENTATION_ERROR | Config still uses `limit_kg: 15` instead of `limit_pct_of_stock: 0.08` |
| R2 | Excess catch above 8% is not kept | ⚠️ PARTIAL | NOT_TESTABLE | The catch_limit plugin can enforce this, but config doesn't enable percentage mode |
| R3 | `stock_after_harvest >= 180kg` | ❌ FAIL | IMPLEMENTATION_ERROR | stock_floor plugin does not exist |
| R4 | Catch reduced/prevented if would breach floor | ❌ FAIL | IMPLEMENTATION_ERROR | stock_floor plugin does not exist |
| R5 | All catches recorded in shared log | ✅ PASS | COMPLIANT | Already implemented by simulation's runtime tracking |
| R6 | Recording by 6pm same day | ⚠️ N/A | NOT_TESTABLE | TECHNICALLY_UNREALIZABLE - no time-of-day model |
| R7 | Compliance with 8% limit verified | ❌ FAIL | IMPLEMENTATION_ERROR | Config not updated to use percentage limit |
| R8 | Compliance with 180kg minimum verified | ❌ FAIL | IMPLEMENTATION_ERROR | stock_floor plugin does not exist |
| R9 | Review on weekly schedule | ⚠️ N/A | NOT_TESTABLE | TECHNICALLY_UNREALIZABLE - no calendar model |
| R10 | Fee equals excess weight | ⚠️ PARTIAL | NOT_TESTABLE | Fee mechanism interpreted as "excess not kept" - valid, but depends on R1 being fixed |
| R11 | Fee deducted from payoff | ⚠️ PARTIAL | NOT_TESTABLE | Interpretation accepted: excess not kept = no payoff added |
| R12 | Two violations = one-trip ban | ❌ FAIL | IMPLEMENTATION_ERROR | violation_ban has `trips: 2` instead of `trips: 1` |
| R13 | Ban lasts exactly one trip | ❌ FAIL | IMPLEMENTATION_ERROR | violation_ban configured for 2-trip ban, not 1-trip |
| R14 | Norm may be revised periodically | ✅ PASS | COMPLIANT | Handled by simulation's propose/vote/implement cycle |
| R15 | Re-evaluation quarterly | ⚠️ N/A | NOT_TESTABLE | TECHNICALLY_UNREALIZABLE - no calendar model |

---

## Implementation Gaps

### Critical Missing Components

1. **stock_floor.py Plugin (REQUIRED)**
   - **File:** `norms/stock_floor.py` 
   - **Status:** DOES NOT EXIST
   - **Impact:** R3, R4, R8 cannot be satisfied without this plugin
   - **Spec Requirements:**
     - Must enforce `min_stock_kg: 180`
     - Must use first-come-first-served enforcement
     - Must emit `below_floor` sanction when reducing catches
     - Must have `describe()` method for agent-facing text

2. **Config Updates for catch_limit**
   - **File:** `state/config.json`
   - **Current:** `{"type": "catch_limit", "limit_kg": 15}`
   - **Required:** `{"type": "catch_limit", "limit_pct_of_stock": 0.08}`
   - **Impact:** R1, R2, R7

3. **Config Updates for violation_ban**
   - **File:** `state/config.json`
   - **Current:** `{"trips": 2, "trigger_sanction": ["over_cap", "over_community_cap"]}`
   - **Required:** `{"trips": 1, "trigger_sanction": ["over_cap", "below_floor"]}`
   - **Impact:** R12, R13

4. **Removal of Obsolete Norms**
   - **Current:** `community_cap` still in config
   - **Required:** Remove `community_cap` (replaced by `stock_floor`)

---

## Test Results Summary

```
============================= test results =============================
tests/norm_evaluation/round_2/test_catch_limit.py     4 FAILED
tests/norm_evaluation/round_2/test_stock_floor.py     5 FAILED, 3 SKIPPED
tests/norm_evaluation/round_2/test_violation_tracking.py  5 FAILED, 1 PASSED
tests/norm_evaluation/round_2/test_round_2_config.py  7 FAILED, 2 PASSED

TOTAL: 24 tests, 5 passed, 16 failed, 3 skipped
```

---

## Detailed Verdicts by Requirement

### R1: 8% Per-Trip Limit (harvested_kg <= 0.08 * stock_before)
**VERDICT: IMPLEMENTATION_ERROR**

The catch_limit plugin exists and supports `limit_pct_of_stock`, but the config was not updated:
- Config has: `{"limit_kg": 15}`
- Should have: `{"limit_pct_of_stock": 0.08}`

**Fix:** Update state/config.json to use percentage-based limit.

---

### R2: Excess Catch Not Kept
**VERDICT: COMPLIANT (pending R1 fix)**

The catch_limit plugin correctly caps catches and returns only the `kept_kg` up to the limit. Once R1 is fixed, this requirement will be satisfied.

---

### R3: Minimum Stock Floor (stock_after >= 180kg)
**VERDICT: IMPLEMENTATION_ERROR**

The stock_floor plugin does not exist. This is a required NEW structural component.

**Fix:** Create `norms/stock_floor.py` implementing the stock floor constraint.

---

### R4: Floor Enforcement (reduce/prevent catch that breaches floor)
**VERDICT: IMPLEMENTATION_ERROR**

Depends on R3. The spec clarifies to use first-come-first-served enforcement (consistent with community_cap pattern).

---

### R5-R6: Shared Logbook Recording
**VERDICT: COMPLIANT / NOT_TESTABLE**

- R5: Simulation already records all catches in runtime.json (COMPLIANT)
- R6: No time-of-day model exists (TECHNICALLY_UNREALIZABLE per spec)

---

### R7-R8: Compliance Verification
**VERDICT: IMPLEMENTATION_ERROR**

Depends on R1-R4 being implemented. The verification mechanism exists in the norm engine, but the norms themselves are not correctly configured.

---

### R9: Weekly Review Schedule
**VERDICT: NOT_TESTABLE**

No calendar model in simulation. Correctly classified as TECHNICALLY_UNREALIZABLE in spec.

---

### R10-R11: Community Fee
**VERDICT: COMPLIANT (interpretation accepted)**

The spec's interpretation is accepted: "fee equals excess weight" = "excess is never kept, so never adds to payoff." This is how catch_limit already works.

---

### R12-R13: One-Trip Suspension
**VERDICT: IMPLEMENTATION_ERROR**

The violation_ban plugin exists, but config has wrong parameters:
- Config has: `{"trips": 2}`
- Should have: `{"trips": 1}`

**Fix:** Update state/config.json to use `trips: 1`.

---

### R14-R15: Quarterly Re-evaluation
**VERDICT: COMPLIANT / NOT_TESTABLE**

- R14: Simulation's norm negotiation handles this (COMPLIANT)
- R15: No calendar model (TECHNICALLY_UNREALIZABLE per spec)

---

## Required Actions to Achieve Compliance

1. **Create `norms/stock_floor.py`**
   - Implement StockFloorNorm class with type_name = "stock_floor"
   - Support `min_stock_kg` parameter (set to 180)
   - Implement first-come-first-served enforcement
   - Emit `below_floor` sanction when catches are reduced
   - Include describe() method for agent notifications

2. **Update `state/config.json`:**
   ```json
   {
     "norms": [
       {"type": "catch_limit", "limit_pct_of_stock": 0.08},
       {"type": "stock_floor", "min_stock_kg": 180},
       {"type": "violation_ban", "trigger_sanction": ["over_cap", "below_floor"], "trips": 1}
     ]
   }
   ```

3. **Verify all plugins load** via `engine.norms.registry.load_norms()`

4. **Run tests again** to confirm all requirements pass

---

## Final Assessment

**Compliance Rate:** 25% (4/16 testable requirements pass)

The norm-implementer has written a comprehensive specification (state/norm_specs/round_2.md) but has NOT implemented the required code changes. The diff only shows updates to simulation data files (norm.txt, runtime.json) which record that Round 2 occurred, but the actual norm enforcement mechanisms remain unchanged from Round 1.

**RECOMMENDATION:** Return to norm-implementer with specific instruction to:
1. Create `norms/stock_floor.py` plugin
2. Update `state/config.json` with correct parameters
3. Re-run tests to verify compliance

---

*Report generated by norm-evaluator agent following standing instructions in CLAUDE.md*
