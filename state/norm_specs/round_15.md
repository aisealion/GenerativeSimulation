**Round 15 Norm Specification**

**Policy (from `norm.txt`)**
- Each fisher may take at most **1.5 kg** per trip when the communal reserve holds at least **30 %** of the lake’s current biomass.
- If the reserve falls below **30 %** of the lake’s biomass, the per‑trip cap is reduced to **1 kg** until the reserve is restored.
- Regardless of the cap, **30 %** of the recorded catch must be deposited into the communal reserve each trip.
- The reserve must always contain at least **30 %** of the lake’s current biomass.

**Implementation Overview**
- A new norm plugin `norms/round_15.py` provides the enforcement.
- `type_name = "round_15"` (used in configuration).
- `describe` reports the current cap (1.5 kg or 1 kg) and the deposit requirement, together with the reserve‑minimum condition.
- `evaluate` determines the applicable cap based on the current reserve level, enforces the cap on the raw catch, records the 30 % deposit, and calculates the kept catch (`max(0, capped - deposit)`).
- `on_round_end` aggregates all deposits into the persistent communal reserve (`context.norm_state(self.key)["reserve_kg"]`). No additional ban logic is required for this round.

**Key Numbers**
- `CAP_DEFAULT_KG = 1.5`    # cap when reserve ≥ 30 % of stock
- `CAP_REDUCED_KG = 1.0`    # reduced cap when reserve < 30 % of stock
- `DEPOSIT_PCT = 0.30`      # 30 % of catch deposited
- `RESERVE_MIN_PCT = 0.30`   # reserve must be ≥ 30 % of stock

**State Keys**
- Persistent reserve balance: `context.norm_state(self.key)["reserve_kg"]`.
- Per‑round scratch data (cleared each round):
  - `deposits` – list of deposit amounts for the communal reserve.
