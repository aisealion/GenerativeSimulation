# Round 1 Norm Specification

**Policy**
Each fisher may harvest no more than **10 kg** per trip. Any excess must be returned to the lake and logged. A simple majority of at least three fishers is required to lift a temporary suspension.

**Operationalization**
1. **Weekly Report** – At the weekly gathering each fisher reports the intended catch.
2. **Quota Setting** – Community sets a shared quota of **10 kg** per person for the upcoming period.
3. **Excess Handling** – If a fisher exceeds the quota, the excess is returned to the lake **immediately** and the fisher records the surplus in the communal log using the action `record surplus in the log`.
4. **Suspension** – If the surplus is **not returned within 48 h**, the fisher’s license status is updated to **"suspended"**.
5. **Lift of Suspension** – The suspension is lifted when:
   - The fisher presents the corrected log entry at the next meeting, **and**
   - A simple majority of the fishers present (minimum three) confirm compliance.
6. **Objection Handling** – If any fisher objects, the lift is postponed until a follow‑up discussion resolves the issue.
7. **Reminder & Enforcement** – Should a fisher fail to comply with the return or log entry, the community delivers a verbal reminder at the next meeting, records a **"reminder"** entry in the ledger, and the fisher must rectify the issue before any further fishing.
8. **Quota Changes** – All changes to the harvest quota require at least three fishers present and a simple majority vote.

**Key Actions & Fluents**
- `record surplus in the log` – logs excess catches.
- `suspended` – fluent indicating a fisher’s license is suspended.
- `reminder` – ledger entry signalling a compliance reminder.

**References**
- Policy and operational details are derived directly from `norm.txt` for round 1.
