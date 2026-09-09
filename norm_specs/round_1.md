# Round 1 Norm Specification

**Policy (from `norm.txt`)**
- Each fisher’s catch is limited to **10 kg per trip**.
- After each trip the fisher must **deposit 2 kg** (20 % of the allowed catch) into the communal reserve.
- The deposit is taken from the fisher’s catch; the fisher keeps the remainder.
- If the deposit is missing or incorrectly reported, the fisher must **make up the shortfall on the next trip** or pay a **fine equal to 5 % of that trip’s total catch, capped at 2 kg**. The fine is added to the communal reserve.

**Implementation Overview**
- A new norm plugin `norms/round_1.py` provides the enforcement.
- `type_name = "round_1"` (used in config).
- `evaluate` enforces the 10 kg cap, subtracts the 2 kg deposit (if possible), and records any shortfall.
- Deposits and fines are accumulated in a per‑round scratch dict and applied to a persistent communal‑reserve balance stored via `context.norm_state`.
- `describe` informs the fisher of the cap and required deposit.
- `on_round_end` updates the communal reserve with total deposits and any fines.

**Key Numbers**
- `CAP_KG = 10.0`
- `DEPOSIT_KG = 2.0`
- `FINE_RATE = 0.05` (5 % of trip catch)
- `FINE_MAX_KG = 2.0`

**State Keys**
- Persistent reserve balance: `context.norm_state(self.key)["reserve_kg"]`.
- Per‑round scratch: `context.round_scratch(self.key)["deposits"]` – list of deposit amounts per agent.
- Per‑round scratch: `context.round_scratch(self.key)["fines"]` – list of fine amounts per agent.
