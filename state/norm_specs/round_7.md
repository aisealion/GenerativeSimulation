# Round 7 Design Specification

**Round number**: 7

**Policy**
- Each fisher may take up to **22 %** of the lake’s current biomass per trip.
- The fisher must **deposit 5 %** of their *catch* into a **communal reserve**.
- Any **over‑quota** catch (exceeding the allowed amount) triggers a **10 % reduction** of the next trip’s allowance. Reductions are **cumulative** until the fisher returns to compliance.
- **Missed deposits** are treated as an over‑quota incident and incur the same 10 % reduction until the deposit is made.
- When the fisher is back within the base 22 % allowance, the reduction factor resets to **1.0** (full allowance).

**Operationalization**
- The norm tracks per‑agent state in `HarvestContext.norm_state(self.key)`:
  - `reduction_factor` – cumulative multiplier applied to the base allowance (starts at 1.0, multiplied by 0.9 for each over‑quota incident).
  - `reserve_kg` – total kilograms deposited into the communal reserve.
- **Evaluation** (`evaluate`):
  1. Compute the base allowance: `0.22 * context.stock_before`.
  2. Apply the current `reduction_factor` to obtain the *effective* allowance.
  3. If `raw_kg` exceeds this allowance, mark over‑quota, multiply `reduction_factor` by 0.9, and record a note.
  4. If the fisher is back within the **base** allowance and a reduction is active, reset `reduction_factor` to 1.0 and note compliance restoration.
  5. Calculate the mandatory deposit: `0.05 * raw_kg` and add it to `reserve_kg`.
  6. Keep the lesser of the proposed catch (from earlier norms) and the effective allowance, then subtract the deposit. The result is the final kept catch.
  7. Return `NormDecision.adjust(kept, note=…)` with an explanatory note.
- **Description** (`describe`): Returns a short sentence for the prompt, showing the current allowance (reduced or full) and reminding the fisher of the 5 % deposit requirement.

**Integration**
- Add the file `norms/round_7.py` (implemented).
- Ensure `state/config.json` includes an entry with `{"type": "round_7"}` to activate the norm for this round.
- No changes required to other engine components; the norm uses the existing `HarvestContext` and `NormDecision` mechanisms.
