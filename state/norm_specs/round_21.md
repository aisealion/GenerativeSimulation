# Round 21 Norm Specification

**Policy**: Each fisher may take up to **20 kg** per trip. A mandatory communal reserve must contain at least **15 %** of the lake’s current stock. At the start of each round every fisher must deposit **0.01 kg** into the reserve; the deposit is forfeited if the fisher fails to log the catch or if the reserve drops below the 15 % threshold. If the reserve falls below 15 % during a round, all fishers’ quotas for that round are automatically scaled down by **20 %**.

**Operationalization**:
- At round start the monitor records stock and computes the 15 % reserve target; each fisher’s 0.01 kg deposit is recorded in round‑scratch `deposits`.
- If a fisher fails to submit a catch log or the reserve is breached, the deposit is retained in the communal reserve (no refund).
- During the round, each fisher’s raw catch is capped at 20 kg. The norm’s `apply` logic will later reduce the kept amount by 20 % if the reserve falls below the threshold (the norm will set a flag `quota_scaled` in persistent `norm_state` and adjust `kept_kg` accordingly).
- At round end the reserve amount is increased by the sum of all `deposits` (including forfeited ones). The norm checks the reserve level; if `< 0.15 * stock_before` it sets `quota_scaled` true so the next round’s quota is reduced by 20 % (the simulation’s norm engine will enforce this scaling for the current round’s decisions).

**State Variables (persisted via `norm_state`)**
- `reserve_kg` – current communal reserve amount.
- `quota_scaled` – bool indicating whether the 20 % quota reduction is active for the current round.

**Round‑scratch variables (transient)**
- `deposits` – list of 0.01 kg deposits recorded per fisher (or forfeited amount).
- `quota_scale_applied` – flag set when the reserve breach occurs.
