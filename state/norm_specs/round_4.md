**Round 4 Norm Specification**

**Policy (from `norm.txt`)**
- Each fisher may take up to **18 % of the lake’s current biomass** per trip.
- The fisher must set aside **5 % of their catch** for the communal reserve.
- If a fisher exceeds their quota, the next trip’s allowance is multiplied by **0.9** for each consecutive over‑quota trip.
- After **three consecutive over‑quota trips** the fisher is **suspended for one trip**.

**Implementation Overview**
- A new norm plugin `norms/round_4.py` provides the enforcement.
- `type_name = "round_4"` (used in config).
- `evaluate` computes the quota from the current stock, applies any over‑quota streak multiplier, records the 5 % deposit, and determines whether the fisher is over‑quota.
- Over‑quota trips are recorded for later streak handling.
- `on_round_end` aggregates deposits into a persistent communal reserve, updates each fisher’s over‑quota streak, and sets a one‑trip suspension flag when the streak reaches three.
- A suspended fisher receives a violation with zero kept catch; the suspension flag is cleared after the suspended trip.

**Key Numbers**
- `BASE_QUOTA_PCT = 0.18`  # 18 % of current stock
- `DEPOSIT_PCT = 0.05`      # 5 % of catch
- `OVERQUOTA_MULT = 0.9`    # 10 % reduction per consecutive over‑quota trip
- `SUSPEND_AFTER = 3`      # consecutive over‑quota trips before suspension

**State Keys**
- Persistent reserve balance: `context.norm_state(self.key)["reserve_kg"]`.
- Per‑agent persistent state (kept in `context.norm_state(self.key)`):
  - `streak` – current consecutive over‑quota count.
  - `suspended` – boolean flag indicating a one‑trip suspension.
- Per‑round scratch data (cleared each round):
  - `deposits` – list of deposit amounts for the communal reserve.
  - `over_quota` – list of agent IDs that exceeded quota this round.
