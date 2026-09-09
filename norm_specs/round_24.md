# Round 24 Norm Specification

**Policy (from `norm.txt`)**
- Maximum catch per fisher per trip: **30 kg**.
- A mandatory reserve of **5 %** of the lake’s pre‑trip stock must be retained at the start of each trip.
- If the reserve falls below this threshold during a round, **all fishers’ quotas are reduced by 20 %** for the next round.

**Implementation Overview**
- New norm plugin `norms/round_24.py` provides enforcement.
- `type_name = "round_24"` (used in config).
- The norm tracks a persistent `quota_multiplier` (default 1.0) which is applied to the base cap of 30 kg. When the reserve falls below the 5 % threshold, the multiplier is set to `0.8` (20 % reduction) for the next round; otherwise it resets to `1.0`.
- `evaluate` enforces the effective per‑trip cap and records no deposit (the norm does not require a deposit); it simply limits kept catch.
- `describe` reports the current effective cap and reserve requirement to the fisher.
- `on_round_end` aggregates any deposits recorded in `round_scratch` under this norm’s key, updates the communal reserve balance, and adjusts the quota multiplier for the next round based on the reserve level.

**Key Numbers**
- `CAP_KG = 30.0` – base maximum catch per trip.
- `RESERVE_PCT = 0.05` – required reserve as a fraction of lake stock.
- `REDUCTION_FACTOR = 0.8` – multiplier applied to the cap when reserve is insufficient (20 % reduction).

**State Keys**
- Persistent reserve balance: `context.norm_state(self.key)["reserve_kg"]`.
- Persistent quota multiplier: `context.norm_state(self.key)["quota_multiplier"]` (1.0 or 0.8).
- Per‑round scratch deposits: `context.round_scratch(self.key)["deposits"]` – list of deposit amounts recorded by this norm (and possibly others) during the round.
