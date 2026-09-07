# Round 18 Norm Specification

**Policy**: Each fisher may take up to **25 % of the lake’s current stock per trip**, capped at **4 kg**. Over the course of a calendar month, a fisher’s **cumulative catch must not exceed 70 % of the lake’s stock at the start of that month**.

**Operationalization**
1. **Per‑trip cap** – the allowed catch for a single trip is the lesser of:
   - `0.25 * stock_before` (25 % of the lake’s stock at the start of the round), and
   - `4.0` kg.
2. **Monthly cumulative cap** – each fisher’s total catch recorded in `HarvestContext.round_scratch` under the key `monthly_quota` is compared against `0.70 * month_start_stock`. The `month_start_stock` is taken as the lake stock at the beginning of the first round of the month (available as `context.stock_before` on that round). If the cumulative catch would exceed the 70 % ceiling, the excess is removed from the keeper’s kept kilograms and a **violation** is recorded.
3. **Violation handling** – when the monthly ceiling is breached, the norm returns a `NormDecision.violation` with:
   - `kept_kg` reduced by the excess amount (down to 0 kg if necessary),
   - a `note` describing the breach, and
   - a `sanction` identifier `monthly_quota_exceeded`.
4. **State tracking** – the norm persists per‑fisher monthly totals in `context.round_scratch(self.key)["catch_by_agent"]`. The cumulative values survive across rounds within the same month. Resetting the month (e.g., on the first round of a new month) is left to external schedule logic.

**Implementation notes**
- The norm is implemented in `norms/monthly_quota_norm.py` with `type_name = "monthly_quota"`.
- No special `on_round_end` logic is required.
- The norm uses the existing `NormDecision` helpers for allowance, adjustment, and violation.
