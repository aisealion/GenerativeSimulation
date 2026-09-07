# Round 6 – Daily Limit Norm Specification

**Norm identifier**: `daily_limit`

**Policy summary** (from `norm.txt`):
- Each fisher may take a maximum of **4 kg per trip**.
- The **community’s total catch per fishing day** must not exceed **30 kg**.
- If an agent’s catch would push the daily total above the cap, the excess is removed from that agent’s kept kilograms (down to zero) and a violation is recorded.

**Operationalization**:
- **Per‑trip cap**: enforced by truncating any `raw_kg` > 4 kg to 4 kg.
- **Daily community total**: tracked in `context.round_scratch('daily_limit')` under the key `daily_total`. Each agent’s kept kilograms are added to this total.
- **Excess handling**: when the prospective daily total would exceed 30 kg, the excess is subtracted from the agent’s kept kilograms (never below 0) and the norm returns a `NormDecision.violation` with a sanction string `"daily_limit_exceeded"` and an explanatory note.
- **State tracking**: per‑agent contributions are stored in `by_agent` within the same round‑scratch dictionary for visibility.

**Implementation notes**:
- Implemented in `norms/daily_limit_norm.py` as class `DailyLimitNorm` extending `engine.norms.base.Norm`.
- `type_name = "daily_limit"` enables automatic discovery via `engine.norms.registry.NORM_TYPES`.
- No special round‑end logic required; `on_round_end` is a no‑op.

**Expected behavior**:
1. An agent catching > 4 kg on a trip will have its catch trimmed to 4 kg and receive a note.
2. As agents harvest, the cumulative `daily_total` is updated.
3. If adding an agent’s kept kilograms would push `daily_total` > 30 kg, the agent’s kept kilograms are reduced accordingly, a violation decision is returned, and a note records the reduction.
4. The sanction `daily_limit_exceeded` can be used by downstream processing (e.g., logging, penalties).
