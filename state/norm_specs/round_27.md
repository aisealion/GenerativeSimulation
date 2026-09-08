# Round 27 Institutional Design Specification

**Policy (norm.txt)**

- Maximum catch per trip: **2 kg**.
- Before fishing, each fisher must deposit the **lesser of 0.5 kg or the intended catch** into a shared pool.
- After removal, at least **15 % of the lake’s pre‑trip stock** must remain.
- The community’s total daily catch may not exceed **80 % of the lake’s weight**.
- Fines are **0.01 kg per excess kilogram** and are added to the shared pool.

**Implementation – `norms/round_27.py`**

- **Class**: `Round27Norm` (`type_name = "round_27"`).
- **Hooks used**: `evaluate` (per‑trip enforcement) and `on_round_end` (daily‑total enforcement).
- **Per‑trip state (scratch)**:
  - `raws`: list of `(agent_id, raw_kg)` for aggregation.
  - `deposits`: each deposit amount.
  - `fines`: fines incurred during the trip.
- **Cross‑round persistent state (norm_state)**:
  - `pool_kg`: cumulative pool balance (deposits + fines).
  - `daily_ban`: boolean flag set when the 80 % daily limit is exceeded.
- **Evaluation flow**:
  1. Record raw catch.
  2. Enforce the 2 kg hard cap – excess is rejected, fine applied, `NormDecision.violation` returned.
  3. Compute deposit (`min(0.5, raw_kg)`) and adjust keep amount.
  4. Check the 15 % stock‑remaining rule – if violated, fisher keeps nothing, fine applied, `NormDecision.violation` returned.
  5. If no violations, return `NormDecision.adjust` with kept kg and a note.
- **End‑of‑round logic**:
  - Sum deposits and fines into `state["pool_kg"]`.
  - Compute total raw catch; if it exceeds `0.80 * stock_before`, calculate a pro‑rata fine for each participating fisher, append to `fines`, and annotate each fisher’s `note` in `round_results`.
  - Set `state["daily_ban"]` accordingly.

**Key Constants (hard‑coded in code)**

- `MAX_CATCH = 2.0`
- `DEPOSIT_MAX = 0.5`
- `MIN_REMAIN_PCT = 0.15`
- `DAILY_MAX_PCT = 0.80`
- `FINE_PER_KG = 0.01`

**Interaction with other norms**

- Placed in the config order after any quota‑type norms (e.g., round 4) so that its per‑trip caps are applied after earlier adjustments.
- Uses only the generic `Norm` API; does not rely on custom hooks, ensuring compatibility with the NormEngine chaining mechanism.
- Does not modify `context.stock_override_kg`; therefore it does not interfere with replenish‑type norms.

**Testing guidance**

- Verify per‑trip enforcement: catches >2 kg, deposit calculation, and 15 % stock rule.
- Verify daily aggregation: total raw >80 % triggers fines and `daily_ban` flag.
- Ensure `state["pool_kg"]` correctly accumulates deposits and fines across rounds.

---

*This file defines the institutional design for round 27 and should be placed at `state/norm_specs/round_27.md`.*
