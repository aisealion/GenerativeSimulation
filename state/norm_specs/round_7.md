# Round 7 – Institutional Design Specification

**Policy**
Each fisher may take a maximum of **4 kg per trip**. The community may not remove more than **25 % of the lake’s current biomass** in any rolling **30‑day** window.

**Operationalization**
- **Per‑trip cap**: Any catch above 4 kg is automatically truncated to 4 kg and the excess is forfeited to the communal pool.
- **Community cap**: At the start of each round the lake stock (`stock_before`) is read. The community‑wide removal limit for the current rolling window is `0.25 * stock_before` kilograms.
- **Rolling window bookkeeping**:
  1. Each norm maintains a persistent list `history` (the total kilograms removed in each of the previous 30 rounds) in `context.norm_state(self.key)["history"]`.
  2. The current round’s cumulative removal is tracked in `context.round_scratch(self.key)["cumulative"]` as agents are processed.
  3. When evaluating an agent, the norm computes the **available allowance** as `limit - (sum(history) + cumulative)`. If the proposed keep would exceed the allowance, it is reduced accordingly and a note is added.
  4. At round end the round’s cumulative total is appended to `history`; if the list exceeds 30 entries the oldest entry is dropped.
- **Forfeiture handling**: Any kilograms trimmed by either the per‑trip or community cap are transferred to the communal pool (recorded via a fact fluent with holder "community").
- **Logging**: Notes are attached to each agent’s decision describing any trimming or deposit actions.

**State interactions**
- Persistent state (`norm_state`) stores the rolling `history` list.
- Round‑scratch state stores the ongoing `cumulative` total for the current round.

**Sanctions**
Violations are non‑punitive adjustments; the norm returns `NormDecision.adjust` with the possibly reduced `kept_kg` and an explanatory note.
