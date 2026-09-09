# Round 28 Norm Specification

**Policy (from `norm.txt`)**
- Maximum catch per fisher per trip: **35 kg**.
- A mandatory reserve of **1 %** of the lake’s pre‑trip stock must be retained at the start of each trip.
- If the reserve falls below this threshold during a round, **all fishers’ quotas are reduced by 25 %** for the next round (the 35 kg cap becomes 26.25 kg per trip).
- A fine of **0.02 kg per kilogram** over the allowed amount is applied; the fine is added to the communal reserve.

**Implementation Overview**
- New norm plugin `norms/round_28.py` provides enforcement.
- `type_name = "round_28"` (used in config).
- The norm tracks a persistent `quota_multiplier` (default 1.0) which is applied to the base cap of 35 kg. When a fine occurs, the multiplier is set to `0.75` (25 % reduction) for the next round; otherwise it resets to `1.0`.
- `evaluate` enforces the effective per‑trip cap, ensures the reserve requirement, and records fines.
- `describe` reports the current effective cap, reserve requirement, and fine details to the fisher.
- `on_round_end` aggregates fines into the communal reserve and adjusts the quota multiplier for the next round based on whether any fines were incurred.

**Key Numbers**
- `BASE_CAP_KG = 35.0` – base maximum catch per trip.
- `RESERVE_PCT = 0.01` – required reserve as a fraction of lake stock.
- `FINE_PER_KG = 0.02` – fine per kilogram over the cap.
- `REDUCTION_FACTOR = 0.75` – multiplier applied to the cap when a fine is incurred (25 % reduction).

**State Keys**
- Persistent reserve balance: `context.norm_state(self.key)["reserve_kg"]`.
- Persistent quota multiplier: `context.norm_state(self.key)["quota_multiplier"]` (1.0 or 0.75).
- Per‑round scratch fines: `context.round_scratch(self.key)["fines"]` – list of fine amounts recorded by this norm during the round.
