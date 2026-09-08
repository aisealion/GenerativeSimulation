# Round 13 Design Specification

**Round number**: 13

**Policy**
- Each fisher may take up to **2 kg** per trip (the *maximum catch*).
- The fisher must **deposit 30 %** of each catch into a **communal reserve**.
- The communal reserve must always hold at least **30 %** of the lake’s current biomass.
- If the reserve falls below the 30 % threshold, the **committee** temporarily reduces the maximum catch for *all* fishers to **1.5 kg** until the reserve percentage reaches 30 % or higher, after which the limit is restored to 2 kg.
- After each trip the fisher logs the catch weight and the deposit weight on the communal ledger **immediately**.
- The **ledger keeper** (rotating monthly) reviews all entries within **24 h**.  A shortfall in the required deposit incurs a **0.05 kg fine** that is added to the communal reserve.
- Any fisher exceeding the 2 kg cap must **return the excess** to the reserve and pay a **0.1 kg fine per kilogram** over the cap; the community suspends that fisher’s license for one day while the fine is added.
- **Weekly**, the committee weighs the communal tank, obtains the lake’s latest biomass from the daily ledger, computes the reserve percentage, and enforces the temporary‑catch‑reduction rule if needed.

**Operationalization**
- The norm stores persistent state in `HarvestContext.norm_state(self.key)`:
  - `reserve_kg` – total kilograms currently in the communal reserve (persistent across rounds).
  - `max_catch_kg` – the active per‑trip cap (2.0 kg by default, 1.5 kg when the reserve is below threshold).
- Per‑round scratch data is kept in `HarvestContext.round_scratch(self.key)`:
  - `ledger_entries` – list of dictionaries `{agent_id, raw_kg, deposit_kg, timestamp}` recorded by fishers.
  - `shortfall_fines_kg` – cumulative fine kilograms from deposit shortfalls.
  - `overcap_fines_kg` – cumulative fine kilograms from catches exceeding the cap.
- **Parameters**
  - `CAP_KG = 2.0`
  - `REDUCED_CAP_KG = 1.5`
  - `DEPOSIT_PCT = 0.30`
  - `RESERVE_MIN_PCT = 0.30`
  - `SHORTFALL_FINE_KG = 0.05`
  - `OVERCAP_FINE_RATE = 0.1`  # kg fine per kg over the cap
- **Hooks**
  - `evaluate(agent, raw_kg)`:
    1. Retrieve the current `max_catch_kg` from state.
    2. If `raw_kg` > `max_catch_kg`, compute excess = `raw_kg - max_catch_kg`.
    3. Apply an over‑cap fine: `fine = OVERCAP_FINE_RATE * excess` kg, add to `overcap_fines_kg` and to `reserve_kg`, and require the excess to be returned.
    4. Compute required deposit = `DEPOSIT_PCT * raw_kg`.
    5. If the fisher’s recorded deposit is less than required, compute shortfall fine = `SHORTFALL_FINE_KG` kg, add to `shortfall_fines_kg` and `reserve_kg`.
    6. Final kept catch = `min(raw_kg, max_catch_kg) - required_deposit` (after adjusting for any fines/returns).
    7. Return `NormDecision.adjust(kept, note=…)`.
  - `on_weekly_check()`:
    1. Committee aggregates all `ledger_entries` to compute the current lake biomass (previous stock minus total kept catches plus voluntary contributions).
    2. Compute `reserve_pct = (reserve_kg / lake_biomass) * 100`.
    3. If `reserve_pct < RESERVE_MIN_PCT * 100`, set `max_catch_kg = REDUCED_CAP_KG` for all agents; otherwise set `max_catch_kg = CAP_KG`.
    4. Record a note for the next round about the active cap.
  - `on_round_end()`:
    - Persist `reserve_kg` and current `max_catch_kg` in the norm state for the next round.
    - Clear per‑round scratch data.

**Integration**
- Add the implementation file `norms/round_13.py` (uses the hooks above).
- Ensure `state/config.json` contains an entry `{"type": "round_13"}` to activate this norm for round 13.
- No other engine modifications are required; the norm relies on existing `HarvestContext`, `NormDecision`, and the weekly committee process already present in earlier rounds.