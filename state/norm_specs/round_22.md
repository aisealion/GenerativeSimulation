# Round 22 Norm Specification

**Policy Statement**
Each fisher may take up to **25 kg** per trip, provided the lake retains at least **10 %** of its current stock as a reserve after the catch. If the reserve falls below 10 %, all quotas are reduced by **20 %** for the following round. Any over‑catch or reserve breach triggers a fine of **0.02 kg** per kg of violation, which is deducted from the fisher’s pre‑paid deposit until settled. A fisher who commits **three or more violations** within any **30‑day (30‑round) window** is temporarily barred from fishing until all fines are cleared.

**Operationalization**
1. When a catch is logged, the system computes the post‑catch lake stock.
2. It verifies that the haul does not exceed 25 kg and that the post‑catch reserve remains ≥ 10 % of the current stock.
3. If either condition is violated, the over‑catch amount (or reserve shortfall) is multiplied by 0.02 kg to obtain the fine, which is deducted from the fisher’s deposit and placed in the community pool.
4. The violation is recorded with a timestamp; the fisher’s violation counter is incremented.
5. If the reserve fell below 10 % in the current round, the fisher’s quota is reduced by 20 % for the next round.
6. After each round, the system reviews all logged violations; if a fisher has three or more violations within any rolling 30‑round window, the fisher is temporarily barred until all outstanding fines are paid.
7. All logs, fines, deposits, and violation counts are stored in a community ledger that is audited monthly at the community meeting.

**Implementation Notes**
- The norm is implemented in `norms/round_22.py`.
- Persistent state (violation history, barred status) is stored via `context.norm_state(self.key)`.
- Per‑round aggregate fines are recorded in `context.round_scratch(self.key)['fines']`.
- The `is_eligible` hook prevents barred fishers from making a LLM call.
- The `on_round_end` hook can be extended to clear temporary flags or adjust future quotas if needed.
