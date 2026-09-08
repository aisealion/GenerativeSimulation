# Round 14 Design Specification

**Round number**: 14

**Policy**
- Each fisher may take up to **1.5 kg** per trip (the *maximum catch*).
- The fisher must **deposit 30 %** of each catch into a **communal reserve**.
- The communal reserve must always hold at least **30 %** of the lake’s current biomass.
- If the reserve falls below the 30 % threshold, the **community votes** each round to choose **one** of the following corrective actions for the *next* round:
  1. Reduce the per‑trip maximum catch to **1 kg** for all fishers.
  2. Increase the required deposit to **40 %** of each catch (an extra 10 % deposit).
- The decision taken for the next round remains in effect until the reserve again meets or exceeds the 30 % threshold, at which point the community may vote to restore the original rules.
- Any fisher who fails to deposit the required amount incurs a **fine equal to the missing deposit** (in kilograms), which is **added to the communal reserve**.
- After each trip the fisher records the raw catch weight and the deposited weight on the communal ledger **immediately**.
- The **ledger keeper** reviews entries each round and updates the reserve balance accordingly.

**Operationalization**
- Persistent state (via `HarvestContext.norm_state(self.key)`):
  - `reserve_kg` – total kilograms currently in the communal reserve (persistent across rounds).
  - `max_catch_kg` – the active per‑trip cap (1.5 kg by default, 1.0 kg when the reduced‑catch rule is active).
  - `deposit_pct` – current required deposit percentage (0.30 by default, 0.40 when the increased‑deposit rule is active).
- Per‑round scratch data (via `HarvestContext.round_scratch(self.key)`):
  - `ledger_entries` – list of dictionaries `{agent_id, raw_kg, deposit_kg, timestamp}`.
  - `fine_kg` – cumulative kilograms of fines collected from deposit shortfalls.
- **Parameters**
  - `CAP_KG = 1.5`
  - `REDUCED_CAP_KG = 1.0`
  - `DEPOSIT_PCT = 0.30`
  - `INCREASED_DEPOSIT_PCT = 0.40`
  - `RESERVE_MIN_PCT = 0.30`
- **Hooks**
  - `evaluate(agent, raw_kg, recorded_deposit_kg)`:
    1. Retrieve `max_catch_kg` and `deposit_pct` from persistent state.
    2. Apply the catch cap: `capped = min(raw_kg, max_catch_kg)`.
    3. Compute required deposit: `required = deposit_pct * raw_kg`.
    4. If `recorded_deposit_kg < required`:
       - `shortfall = required - recorded_deposit_kg`
       - Add `shortfall` to `fine_kg` and to `reserve_kg` (fine is paid to reserve).
    5. Record the ledger entry with the actual deposit.
    6. Final kept catch = `capped - recorded_deposit_kg` (deposits are removed from the fisher’s haul).
    7. Return `NormDecision.adjust(kept_kg=final_kept, note=…)`.
  - `on_round_end(context, round_results)`:
    1. Aggregate deposits and fines from scratch into the persistent `reserve_kg`.
    2. Compute current lake biomass via `context.stock_before` and the round’s harvested totals.
    3. Calculate `reserve_pct = reserve_kg / lake_biomass`.
    4. If `reserve_pct < RESERVE_MIN_PCT`:
       - The community votes (simulated by configuration flag `next_action`).
       - If the vote selects **reduced cap**, set `max_catch_kg = REDUCED_CAP_KG` and `deposit_pct = DEPOSIT_PCT`.
       - If the vote selects **increased deposit**, keep `max_catch_kg = CAP_KG` and set `deposit_pct = INCREASED_DEPOSIT_PCT`.
    5. If `reserve_pct >= RESERVE_MIN_PCT`, reset to default `max_catch_kg = CAP_KG` and `deposit_pct = DEPOSIT_PCT`.
    6. Persist the updated `max_catch_kg`, `deposit_pct`, and `reserve_kg` in norm state for the next round.
    7. Clear per‑round scratch data.

**Integration**
- Add implementation file `norms/round_14.py` that follows the hooks described above.
- Ensure `state/config.json` contains an entry `{"type": "round_14"}` to activate this norm for round 14.
- No changes to the core engine are required; the norm uses existing `HarvestContext`, `NormDecision`, and the voting mechanism already present in earlier rounds.

```json
{
  "classification": "success"
}
```