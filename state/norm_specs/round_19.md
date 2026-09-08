# Round 19 Norm Specification

**Policy Overview**
- Each fisher may keep up to **20 kg** of fish per trip.
- A mandatory communal reserve must contain at least **12 %** of the lake’s current stock.
- If at any point the reserve falls below this 12 % threshold, the per‑fisher quota for the *next* round is reduced by **20 %** (e.g., 20 kg → 16 kg). The reduced quota persists until the reserve recovers above the threshold.
- Violations (exceeding the quota or causing the reserve to dip below 12 %) incur a fine of **0.03 kg** per violation, which is added to a communal lake‑maintenance pot.

**Operational Details**
1. **Lake Keeper Election** – At the start of each round the community elects a Lake Keeper (simple majority). The Keeper measures the lake’s stock, computes the reserve (12 % of stock), and announces the current quota.
2. **Quota Enforcement** – During the round the Keeper monitors every fisher’s trip. Any trip that would:
   - exceed the announced quota, or
   - reduce the communal reserve below 12 % of the stock
   is refused.
3. **Fine Collection** – For each refused trip the Keeper records a fine of 0.03 kg, added to the communal maintenance pot.
4. **Reserve Monitoring & Quota Adjustment** – At round end the Keeper checks the reserve level:
   - If reserve < 12 % of stock, the Keeper announces a **20 % quota reduction** for the next round and publishes the new limits.
   - If reserve ≥ 12 % at round start, the quota remains at the current level.
5. **State Management** – The Keeper (implemented as a norm) updates persistent state to track:
   - Current reserve amount.
   - Current per‑fisher quota.
   - Accumulated fines in the communal pot.

**State Variables (persisted via `norm_state`)**
- `reserve_kg` – Current communal reserve amount (kg).
- `quota_kg` – Current per‑fisher maximum catch (kg).
- `fine_kg` – Total fines collected this round (kg), stored in communal pot.

**Round‑scratch variables (transient)**
- `deposits` – List of fine amounts recorded for this round (each 0.03 kg).
- `refusals` – List of agent IDs whose trips were refused this round.
