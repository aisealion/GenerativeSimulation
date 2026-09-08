# Round 33 Norm Specification

**Policy**

- Each fisher may take up to **90 % of the lake’s current biomass** per trip.
- If the **communal reserve is below 5 kg**, the fisher must **deposit 10 % of their catch** into the reserve.
- If the reserve falls below **3 kg**, the maximum take for the **following trip** is reduced by **30 %** (i.e., the fisher may only take 70 % of the lake biomass). This reduction persists until the reserve reaches at least **5 kg**.
- **Violations** (exceeding the quota or failing to meet deposit requirements) trigger:
  1. A **10 % fine** on the excess catch, recorded as a revenue entry.
  2. Immediate correction (excess catch/confiscated to the reserve).
  3. A **20 % temporary quota reduction** for the next **two trips**.
  4. **Repeat offenders** are **permanently excluded** from fishing until the reserve is replenished to **≥ 5 kg**, after which the exclusion flag is cleared.

**Operationalization**

1. **Start‑of‑Trip**
   - The keeper logs the current lake biomass (`stock_before`) and the communal reserve balance.
   - The fisher declares a desired catch.
   - The keeper calculates the **90 % quota** based on `stock_before`.
   - If the reserve `< 5 kg`, the keeper mandates a **10 % deposit** of the declared catch; the deposit amount is added to the reserve.
   - If the reserve `< 3 kg`, the keeper applies a **30 % quota reduction** for the **next trip** (stored in per‑agent norm state).

2. **During the Trip**
   - If the actual catch exceeds the quota, the keeper orders the excess to be returned **or confiscated** into the reserve.
   - The excess is recorded, a **10 % fine** on the excess is logged (capped by policy if needed), and the fisher’s net catch is adjusted.
   - If the deposit rule applies and the catch is insufficient to cover the required 10 % deposit, the same fine and correction logic is used.

3. **End‑of‑Trip**
   - The keeper updates the communal ledger with:
     - New reserve balance (including deposits, fines, and confiscated excess).
     - Any **quota‑reduction flags** (20 % for the next two trips) attached to the fisher’s record.
     - **Exclusion flag** for repeat violators.
   - A weekly audit by the community steward verifies ledger entries against physical fish and reserve measurements, correcting discrepancies immediately.

4. **State Management** (implemented in the norm plugin)
   - `norm_state` stores per‑agent data:
     - `streak`: count of consecutive violations for applying the 20 % temporary reduction.
     - `excluded`: boolean flag indicating permanent exclusion.
     - `reduction_active`: boolean flag for the 30 % reduction when reserve `< 3 kg`.
   - `round_scratch` aggregates round‑level data:
     - `deposits`, `fines`, `confiscated_excess` for reserve updates.

5. **Ban / Exclusion Handling**
   - When a fisher is flagged as `excluded`, they receive **zero catch** for the trip and a note indicating permanent exclusion until the reserve ≥ 5 kg.
   - After each round, the norm checks the reserve; if it meets the threshold, the `excluded` flag is cleared for that fisher.

**Implementation Notes**

- The norm class should be named `Round33Norm` with `type_name = "round_33"`.
- Hooks to implement:
  - `describe` – returns a human‑readable summary of the current constraints.
  - `evaluate` – applies the cap, deposit requirement, fine logic, and updates `round_scratch`.
  - `on_round_end` – aggregates deposits/fines, updates the communal reserve, manages quota reductions, and clears exclusion flags when the reserve is replenished.
- All monetary/penalty values are expressed in **kg** for consistency with existing norms.
- Ensure that the norm respects the ordering in `state/config.json` – later norms may depend on the updated reserve value.
