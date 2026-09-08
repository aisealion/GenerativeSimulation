# Round 31 Norm Specification

**Policy**: Each fisher may take up to **35 kg** per trip, provided the lake retains at least **5 %** of its pre‑catch stock. If the communal reserve falls below **5 %** of that pre‑catch stock, the fisher must surrender **1 kg** of fish for every **1 kg** the reserve is short. When this occurs, the keeper announces a **20 % reduction** in all individual quotas for the next round. Failing to submit a catch log incurs a **0.5 kg fine** and a **one‑round suspension**.

**Operationalization**:
1. The keeper is elected each round (same voting mechanism as policy proposals).
2. Before each trip the keeper records the lake’s current stock (pre‑catch).
3. After the trip the keeper records the catch weight and calculates the post‑catch reserve.
   - If reserve < 5 % of pre‑catch stock, the shortfall (in kg) is surrendered by the fisher to the communal reserve.
   - The keeper records the surrender amount for aggregation.
4. At round end the keeper releases **10 %** of the current reserve back into the lake.
5. If the reserve remains below 5 % for two consecutive rounds, the keeper may:
   - Use part of the reserve for restocking projects, **or**
   - Reduce future quotas for repeat violators.
6. If the reserve is still below 5 % after the round, the keeper announces a **20 % quota reduction** for the next round.
7. A fisher who fails to submit a catch log is fined **0.5 kg** and suspended for one round.

**Implementation Details (norms/round_31.py)**:
- **Quota enforcement**: hard cap of 35 kg per trip.
- **Lake‑stock safety**: ensures at least 5 % of pre‑catch stock remains; excess catch is surrendered.
- **Reserve shortfall**: if communal reserve < 5 % of pre‑catch stock, fisher surrenders 1 kg per kg shortfall (up to what they keep).
- **Reserve tracking**: `norm_state` stores `reserve_kg`, `low_reserve_streak`, and flags for quota reduction.
- **End‑of‑round actions**:
  - Aggregate surrendered fish into the reserve.
  - Release 10 % of the reserve back to the lake via `context.override_stock_after_regrowth`.
  - Update low‑reserve streak and optional restocking support.
  - Clear quota‑reduction flags after announcement.
- **Missing log handling**: (not directly enforced here; other infrastructure should apply the fine/suspension).

**Notes**:
- The norm records surrendered amounts in `round_scratch(...).setdefault("surrenders", [])` for later aggregation.
- The quota‑reduction flag is stored in `norm_state` so that external components can read it to adjust future quotas.
- All numeric constants are defined at the top of the file for easy tuning.
