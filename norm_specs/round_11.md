# Round 11 – Monthly Limit Norm Specification

**Norm identifier**: `monthly_limit_11`

**Policy summary** (from `norm.txt`):
- Each fisher may take up to **3 kg per trip**.
- Each fisher must retain at least **1 kg for personal use** per trip.
- The **community’s total monthly catch** may not exceed **50 % of the lake’s current stock at the start of the month**, capped at **10 kg**.
- Any **overage must be returned** to the communal fund before the next month.
- Failure to return the required share results in a **temporary loss of fishing privilege** (or an equivalent penalty).

**Operationalization**:
1. **Monthly stock estimation** – At the beginning of each month, all fishers collectively estimate the lake’s current stock via a quick sampling method. The result is recorded by the rotating log keeper in the shared ledger (`context.stock_before` provides the stock at the start of the month for the first round of that month).
2. **Per‑trip limits** – Each fisher records the total catch of a trip and sets aside **1 kg** for personal use. The remaining catch is the *harvestable* amount. If the total catch exceeds **3 kg**, it is trimmed to **3 kg** and a note is added.
3. **Monthly aggregation** – At month’s end, the log keeper compiles every fisher’s harvestable catch into a community ledger (`monthly_total`). The ledger also tracks each fisher’s individual contribution.
4. **Cap enforcement** – The ledger’s total community catch is compared to the lower of:
   - **50 % of the month‑start stock** (`0.5 * context.stock_before`), and
   - **10 kg**.
   If the total exceeds this limit, the excess (`overage`) is calculated.
5. **Overage allocation** – The overage is proportionally allocated to each fisher based on their individual harvestable contribution. Each fisher must return their share to the communal fund within the first two days of the next month.
6. **Penalty handling** – If a fisher fails to return the required share, the log keeper records a debt and marks the fisher for a **temporary loss of fishing privilege** (or an equivalent community‑determined sanction). This status can be represented via a norm‑specific sanction string, e.g., `monthly_overage_penalty`.

**Implementation notes**:
- The norm should be implemented as a subclass of `engine.norms.base.Norm` (e.g., `MonthlyLimit11Norm`).
- `type_name = "monthly_limit_11"` enables discovery via the registry.
- Per‑trip trimming and personal‑use retention can be handled in `evaluate` by adjusting `raw_kg` to `max(min(raw_kg, 3.0) - 1.0, 0.0)` and attaching an appropriate note.
- Monthly aggregation and cap enforcement require state persisted across rounds of the same month. Use `context.norm_state(self.key)` for cross‑round persistent storage of:
  - `month_start_stock`
  - `monthly_total`
  - `by_fisher` contributions
- At the start of a new month, reset these fields.
- Over‑age calculation and proportional allocation can be performed in `on_round_end`. The norm should emit a `NormDecision.violation` for each fisher who must return catch, with a sanction string such as `monthly_overage` and a note describing the required return amount.
- Penalty enforcement (temporary loss of privilege) can be signaled via a separate sanction or by setting a flag in the fisher’s persistent state that other norms (e.g., a ban norm) can read.

**Expected behavior**:
1. Trips exceeding 3 kg are trimmed; trips below 1 kg result in a kept amount of 0 kg (the fisher retains the mandatory 1 kg, which is not part of the harvestable pool).
2. The community ledger accurately tracks total harvestable catch for the month.
3. If the monthly total surpasses the allowed cap, each fisher receives a violation decision indicating the amount they must return.
4. Fisher(s) who do not return the required share are recorded with a sanction that downstream logic can interpret as a temporary fishing ban.
5. All state resets correctly at the beginning of a new month.
