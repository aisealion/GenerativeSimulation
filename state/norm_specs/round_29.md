# Round 29 Norm Specification

**Policy (as defined in `norm.txt**):**
- Each fisher may take up to **35 kg** per trip, provided the lake retains at least **1 %** of its pre‑trip stock as a reserve.
- A reserve violation triggers a **fine of 1 kg** per kilogram of reserve lost **and** a **20 % quota reduction** for the next round.
- A **compliance score** starts at **100 %** and loses **5 %** for each reserve violation **or** quota breach (catch > 35 kg) **or** fine.
- **Lift criteria** to restore the default quota:
  1. No reserve violations in the **last five trips**.
  2. No fines — i.e., no reserve violations — in the **last three trips**.
  3. Compliance score ≥ **90 %**.
  4. (Stewardship report within 48 h – omitted from this implementation.)

**Implementation Overview (`norms/round_29.py`):**
- Defines `Round29Norm` subclass of `Norm` with `type_name = "round_29"`.
- Tracks per‑fisher persistent state via `context.norm_state(self.key)`:
  - `quota_kg` – current quota (default 35 kg, reduced to 28 kg after a reserve violation).
  - `compliance_score` – starts 100 %, drops 5 % per violation.
  - `reserve_violations` list – recent reserve‑violation flags (trimmed to 5 entries).
  - `fines` list – recent fine flags (trimmed to 3 entries).
- `describe` reports the current quota and reserve requirement.
- `evaluate` enforces the quota and reserve rule:
  - If reserve after catch falls below 1 % of pre‑trip stock, compute shortfall, apply a fine equal to the shortfall, deduct the fine from the kept catch, and record the fine.
  - If the catch exceeds the quota, note the breach (affects compliance but not fine).
  - Updates compliance score and reduces quota for the next round when a reserve violation occurs.
- `on_round_end` trims history lists, checks lift criteria, and restores the default quota when satisfied.

**Key Constants**
- `DEFAULT_QUOTA_KG = 35.0`
- `RESERVE_MIN_PCT = 0.01`
- `COMPLIANCE_PENALTY = 5.0`
- `QUOTA_REDUCTION_FACTOR = 0.8` (20 % reduction)
- `LIFT_COMPLIANCE_THRESHOLD = 90.0`
- `MAX_RESERVE_VIO_HISTORY = 5`
- `MAX_FINE_HISTORY = 3`

This specification together with the code implements the round 29 norm as described in `norm.txt`.