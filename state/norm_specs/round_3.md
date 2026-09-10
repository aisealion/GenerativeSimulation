# Round 3 Norm Specification

**Policy**

- Each fisher may keep up to **20 kg** of fish per trip. Any amount beyond 20 kg must be placed into the **community reserve**.
- The reserve may be used only:
  1. In **emergencies**, up to **5 % of the current reserve** per event (rounded down to whole kg).
  2. For **routine maintenance** after communal meals, using **5 % of the current reserve** (rounded down).
- Fish taken from the reserve are **returned after use**, and the reserve inventory is recorded **weekly** by the **Lake Monitor**.

**Operationalization**

1. Fisher counts catch before returning to shore; excess (> 20 kg) is deposited into the locked reserve bin.
2. The Lake Monitor weighs and logs the reserve bin each week, noting the total kilograms.
3. For an emergency or routine‑maintenance event, the Lake Monitor announces the event, calculates 5 % of the current reserve (rounding down), logs the removal, and authorizes that amount for use.
4. Fish removed from the reserve are used; once the event completes, they are returned to the bin and the reserve total is updated.
5. Violations of the 20 kg limit or failure to return reserve fish are logged; the fisher must surrender the excess, or repeated offenses trigger a **two‑week fishing ban** and/or mandatory maintenance duty, enforced by the Lake Monitor and the community via a simple‑majority meeting.
6. The **Lake Monitor** role rotates monthly to the fisher who has served the longest, ensuring neutrality.
7. The **Mayor** is elected annually by all fishers; the mayor appoints a council of three respected fishers for two‑year terms, meeting monthly to review lake conditions and authorize emergencies.
8. The **Maintenance Committee** consists of five members: the Lake Monitor, the fisher with the most years fishing, a fisher elected by majority vote, the boat operator, and a youth representative; the committee is re‑selected each season.
9. After each communal meal, **5 % of the current reserve** is set aside for routine maintenance, rounded down to the nearest kilogram.

**Fluents introduced**

| fluent name | represents |
|---|---|
| `reserve_balance` | Current kilograms stored in the community reserve. |
| `reserve_withdrawal` | Kilograms withdrawn from the reserve for an event. |
| `reserve_return` | Kilograms returned to the reserve after use. |
| `monitor_role` | Identifier of the current Lake Monitor. |
| `violation_count` | Number of recorded violations for a fisher in the current round. |
| `ban_active` | Boolean flag indicating whether a fisher is currently under a fishing ban. |
| `maintenance_allocation` | Kilograms earmarked for routine maintenance after each communal meal. |

**Norm implementation notes**

- Implement a `CatchLimitNorm` (or similar) subclass in `norms/catch_limit_reserve.py` with `type_name = "catch_limit_reserve"`.
  - In `evaluate`, enforce the 20 kg per‑trip cap, move excess to the reserve via `NormDecision.adjust`, and record a violation when the cap is exceeded.
- Implement a `ReserveManagementNorm` subclass in `norms/reserve_management.py` with `type_name = "reserve_management"`.
  - Provide `on_event` hooks for emergencies and routine‑maintenance events to calculate the 5 % withdrawal, update `reserve_balance`, and handle returns.
  - Enforce the weekly inventory logging in `on_weekly_update`.
- Implement a `ViolationNorm` subclass to apply bans and mandatory maintenance duties after repeated violations.
- Register the new norm types in `state/config.json` under the `norms` array, e.g. `{ "type": "catch_limit_reserve" }`, `{ "type": "reserve_management" }`, `{ "type": "violation" }`.
- Add the new fluents to `state/fluents_schema.md` as shown above.
- Update `state/institution.json` `norm_types` catalog to include the three new `type_name`s.
- Ensure role‑rotation logic for the Lake Monitor is handled in the appropriate governance norm (e.g., `norms/rotating_board.py`).
