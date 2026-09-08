# Round 20 Norm Specification

**Policy**: Each fisher may take up to **30 kg** per trip. Any catch above this cap is deposited as a fine into the communal reserve. The reserve must remain at least **5 %** of the lake’s current stock. If the reserve falls below this threshold, the quota for the following round is reduced by **20 %** for all fishers.

**Operationalization**:
- After each trip, the agent keeps `min(catch, 30)` kg.
- Excess (`catch - 30` kg, if any) is added to the reserve via `deposits` recorded in the norm's round‑scratch state.
- At round end, the reserve is increased by the sum of all deposits.
- The norm tracks `reserve_kg` in persistent `norm_state`.
- If `reserve_kg` < `0.05 * stock_before`, the flag `quota_reduction_active` is set true; the simulation’s next‑round logic should apply a 20 % quota reduction.
