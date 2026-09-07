# Round 20 Norm Specification

**Policy**
- Each fisher may take up to **30 % of the lake’s current stock per trip**, capped at **4 kg**.
- A fisher may not cumulatively take more than **60 % of the lake’s stock at the start of each calendar month**.

**Operationalization**
1. **Monthly baseline measurement** – On the first fishing day of each month, the designated lake monitor (rotated each month) measures the lake’s total fish stock and records the baseline in the shared ledger.
2. **Trip‑level logging** – After each trip, every fisher logs their catch immediately on the ledger, noting weight and time.
3. **Daily ledger review** – The ledger is reviewed daily by the community; if a fisher’s log exceeds **30 % of that month’s baseline or 4 kg**, the excess is returned to the lake and the fisher sits out the next fishing day.
4. **Cumulative monthly tracking** – The cumulative monthly catch of each fisher is tracked; if it exceeds **60 % of the initial stock**, the fisher must return the excess and sit out the next day.
5. **Stewardship** – The lake monitor also serves as the fishing steward for the month, mediating disputes and ensuring ledger accuracy.
6. **Quarterly review** – Quarterly, the community reviews the average initial stock of the past three months; if it consistently stays above **5 kg**, any fisher may propose increasing the **60 % monthly cumulative limit**.
7. **Proposal adoption** – Proposals are discussed at the next community meeting and require a simple majority (or **2/3** if agreed) to adopt the new limit, which then takes effect on the first fishing day of the following month.

**Implementation Notes**
- The norm should be added to `norms/` as a subclass of `engine.norms.base.Norm` with `type_name = "round_20"`.
- Use `HarvestContext.norm_state` to persist any necessary state (e.g., baseline stock, monthly totals).
- Enforce per‑trip caps in `evaluate`, and apply cumulative monthly caps in `on_round_end`.
- Record sanctions via `NormDecision.violation` with identifiers such as `"trip_limit_exceeded"` or `"monthly_cumulative_exceeded"`.
- Update the ledger and handle steward rotation as defined in the simulation’s existing infrastructure.

---
*Prepared for round 20 of the simulation as dictated by `norm.txt`.*
