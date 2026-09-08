# Round 16 Norm Specification

**Policy Overview**
- Maximum catch per fisher per trip starts at **1.5 kg**.
- Each fisher must deposit **30 %** of the kept catch into the communal reserve.
- The communal reserve must always hold at least **30 %** of the lake’s current biomass.
- If the reserve falls below this threshold, the community reduces the per‑fisher maximum catch by **0.1 kg** (minimum 0 kg). The reduced limit remains until the reserve recovers.
- If the reserve stays at or above the threshold for **two consecutive rounds**, the limit is increased by **0.1 kg** (capped at the original 1.5 kg).
- A shortfall in the required deposit incurs a fine of **0.05 kg** per kilogram shortfall. Fines are carried forward per fisher and deducted from future kept catch.

**Operational Details**
1. **Catch Capping** – The raw catch reported by the fisher is capped at the current per‑fisher limit.
2. **Deposit** – After capping, 30 % of the kept catch is deposited into the communal reserve.
3. **Fine Calculation** – If the required deposit (30 % of the *raw* catch) exceeds the actual deposit (because the catch was capped), the shortfall is multiplied by 0.05 kg and added to the fisher’s fine balance.
4. **Reserve Management** – At round end, all deposits are added to the communal reserve.
5. **Limit Adjustment** –
   - If reserve < 30 % of lake biomass → reduce limit by 0.1 kg per fisher for the next round.
   - If reserve ≥ 30 % for two consecutive rounds → increase limit by 0.1 kg per fisher, not exceeding 1.5 kg.
6. **Fine Enforcement** – At the start of each round, any outstanding fine balance is subtracted from the fisher’s allowed kept catch.

**State Variables (persisted via `norm_state`)**
- `limit_kg` – Current per‑fisher maximum catch.
- `reserve_kg` – Current communal reserve amount.
- `consecutive_good` – Counter of consecutive rounds with reserve ≥ 30 %.
- `fine_balances` – Mapping `{agent_id: fine_kg}`.

**Round‑scratch variables (transient)**
- `deposits` – List of deposit amounts for this round.
- `penalties` – List of fine amounts applied this round.
