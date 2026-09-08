**Round 4 Norm Specification**

**Policy (from `norm.txt`)**
- Each fisher may take up to **80 % of the lake’s current biomass** per trip.
- **10 % of each catch** is deposited into the communal reserve.
- If the reserve falls below **5 kg**, the next trip’s maximum take is reduced by **20 %** (to **64 % of lake biomass**) and remains reduced until the reserve reaches **10 kg**.
- Failure to deposit or exceeding the quota triggers a **0.01 kg fine** and a **0.01 kg restitution** to the reserve.

**Operationalization**
1. Before every trip the fisher checks the current lake biomass **B** and the communal reserve total **R** (posted on the notice board or shared ledger).
2. The allowed take **T** is:
   - `0.8 × B` if `R ≥ 5 kg`
   - `0.64 × B` if `R < 5 kg` (reduced quota).
3. After fishing the fisher records the catch **C**.
4. The fisher must transfer `0.1 × C` into the communal reserve ledger.
5. If `C > T` **or** the 10 % deposit was not made, the fisher pays a fine of **0.01 kg** and immediately restitutes **0.01 kg** to the reserve.
6. The Reserve Keeper (rotating weekly to the fisher with the highest net catch that week) signs the ledger each day and posts the reserve balance.
7. The community council meets weekly to audit the ledger, confirm the reserve level, and if `R ≥ 10 kg` the quota returns to **80 %** for the next trip; otherwise the reduced quota persists.

**State Keys**
- Persistent reserve balance: `context.norm_state(self.key)["reserve_kg"]`.
- Per‑agent temporary data (e.g., last trip’s catch, fine status) may be stored in `context.norm_state(self.key)[agent_id]` as needed.

**Implementation Overview**
- A norm plugin `norms/round_4.py` implements the above logic in its `evaluate` and `on_round_end` methods.
- `type_name = "round_4"` is used in the simulation configuration.
