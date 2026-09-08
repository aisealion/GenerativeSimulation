# Round 9 Design Specification

**Round number**: 9

**Policy**
- Each fisher may take up to **2 kg** per trip.
- The fisher must **deposit 30 %** of their *catch* into a **communal reserve**.
- Failure to deposit the required 30 % or exceeding the 2 kg limit triggers a **10 % fine** on the excess fish, which is deposited into the communal reserve; any remaining excess fish are returned to the lake.

**Operationalization**
- The norm tracks per‑agent state in `HarvestContext.norm_state(self.key)`:
  - `reserve_kg` – total kilograms deposited into the communal reserve (persistent across rounds).
  - `fine_kg` – cumulative kilogram amount of fines owed by the agent (reset each round after payment).
- **Evaluation** (`evaluate`):
  1. Compute the base allowance: `min(2.0, 0.30 * context.stock_before)` – the 2 kg cap is absolute, but the deposit requirement is relative to the catch.
  2. If `raw_kg` > 2 kg, calculate excess = `raw_kg - 2.0`.
  3. Apply a 10 % fine on the excess: `fine = 0.10 * excess`.
  4. Add the fine to `fine_kg` and deposit the fine amount into `reserve_kg`.
  5. Determine the mandatory deposit: `deposit = 0.30 * raw_kg`.
  6. If the fisher deposited less than `deposit`, treat the shortfall as an additional fine of `0.10 * (deposit - actual_deposit)` and add it to `fine_kg`/`reserve_kg`.
  7. Reduce the kept catch by the required deposit and any fine amount, returning the remainder as `kept_kg`.
  8. Return `NormDecision.adjust(kept_kg, note=…)` with a note describing any fine or deposit shortfall.
- **Description** (`describe`): Returns a sentence for the prompt, stating the 2 kg cap and the 30 % deposit requirement, and, if a fine is pending, informs the fisher of the fine amount.

**Integration**
- Add the file `norms/round_9.py` (implementation to be added).
- Ensure `state/config.json` includes an entry `{"type": "round_9"}` to activate this norm for round 9.
- No changes required to other engine components; the norm uses existing `HarvestContext`, `NormDecision`, and the communal reserve tracking already present in earlier norms.
