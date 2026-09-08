# Round 35 Norm Specification

**Policy (as defined in `norm.txt`):**
- Each fisher may take up to **70 %** of the lake’s current stock per trip.
- Fisher must leave at least **5 %** of that stock as a communal reserve.
- If the reserve is insufficient, a **fine of 1 kg per kg** of reserve lost is imposed.
- All fines are added to a **communal reserve**.
- If the communal reserve falls below **5 %** of the lake stock for **two consecutive rounds**, quotas for the next round are reduced by **20 %**.

**Implementation (`norms/round_35.py`):**
- Constants: `BASE_QUOTA_PCT = 0.70`, `RESERVE_PCT = 0.05`, `LOW_RESERVE_PCT = 0.05`, `REDUCTION_FACTOR = 0.80`.
- Persistent state via `context.norm_state(self.key)` tracks:
  - `reserve_kg` – current communal reserve (accumulated fines).
  - `low_reserve_streak` – consecutive rounds where reserve < 5 % of stock.
  - `quota_multiplier` – 1.0 normally, 0.80 after two low‑reserve rounds (20 % quota reduction).
- Per‑round scratch stores collected `fines` for aggregation.
- **`evaluate`** caps raw catch at the (possibly reduced) quota, computes required reserve, applies fines when reserve shortfall occurs, updates communal reserve, and returns an adjusted `NormDecision`.
- **`on_round_end`** updates the low‑reserve streak, adjusts `quota_multiplier` for the next round, and ensures the communal reserve is persisted.

**Design Rationale:**
- The norm follows the exact textual policy, translating reserve shortfalls into monetary‑like fines deducted from kept catch.
- Persistent state enables tracking of reserve levels across rounds and applying the 20 % quota reduction only after two consecutive low‑reserve rounds, matching the policy.
- The implementation uses the existing `Norm` contract and `NormDecision` helpers, ensuring compatibility with the `NormEngine` orchestration.

**Testing Considerations:**
- Verify quota caps respect `quota_multiplier`.
- Confirm fines are correctly calculated and deducted.
- Ensure communal reserve updates and low‑reserve streak logic trigger the 20 % quota reduction after two qualifying rounds.
- Edge cases: fine larger than kept catch should not produce negative kept kg.
