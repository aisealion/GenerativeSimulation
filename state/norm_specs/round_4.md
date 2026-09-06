# Round 4 Norm Specification

**Policy:** Fishing is permitted only when lake stock exceeds 10 kg; each fisher may catch up to 2 kg per trip and the community may harvest no more than 30 % of the current lake stock each day; all catches and penalties are recorded in a shared ledger with daily stock counts verified by rotating fishers; penalties are community‑labor days scheduled by the ledger and reviewed by Kai; the rule is reviewed monthly to adjust the 10 kg threshold if needed.

**Operationalization:**
1. Each morning the fisher scheduled for the day (rotating list) estimates the lake stock by visual or a sample net weight and records the value in the ledger under "Stock_Count." Two randomly chosen fishers independently verify and record the same estimate; all entries are timestamped.
2. If Stock_Count < 10 kg, all fishing is suspended that day; no catches are recorded.
3. If Stock_Count ≥ 10 kg, compute the daily harvest limit as 0.30 × Stock_Count. The maximum number of fishers allowed to fish that day is floor((0.30 × Stock_Count)/2). If more fishers plan to fish, postpone or limit the number accordingly.
4. Each allowed fisher receives a 2 kg quota; this is logged in the ledger under "Quota".
5. When a fisher returns, they record their actual catch under "Catch." If Catch > Quota, the excess is added to the communal reserve and the ledger logs the excess amount under "Excess".
6. If a fisher exceeds their quota, the ledger assigns a penalty: Penalty_Date is set to the first non‑fishing day after the violation (or the next available non‑fishing day if fishing is suspended). Penalty_Task is set to a simple community labor task (e.g., net repair, dock cleaning). The fisher signs the ledger after completing the task, and two witness fishers sign as well; Kai reviews the signatures during the daily check‑in and marks Penalty_Completed = "Yes".
7. If Penalty_Completed remains "No" after 2 days, Kai calls a community meeting to discuss the outstanding penalty.
8. Monthly, the community reviews the lake’s stock trend; if the average stock is steadily above the 10 kg threshold for 3 consecutive months, the threshold may be increased; if below, it may be decreased. All changes are recorded in the ledger and communicated to the fishers.
9. Ledger columns: Fisher_ID, Trip_Date, Stock_Count, Quota, Catch, Excess, Penalty_Date, Penalty_Task, Penalty_Completed. All entries are time‑stamped and accessible to all fishers.
