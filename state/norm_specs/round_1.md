# Round 1 Norm Specification

**Policy**

- No fisher may harvest more than **10 %** of the lake’s current stock in a single trip.
- The lake must retain at least **25 %** of its stock for natural regeneration.
- Any catch above the 10 % limit is logged and the excess, plus a **10 % catch‑tax** (1 kg → 1 community credit), is transferred to the community reserve fund.
- When the lake’s stock falls below the 25 % threshold, a **temporary moratorium** is imposed.
- The moratorium is lifted only after **two consecutive quarterly surveys** confirm the stock is at or above 25 %.

**Operationalization**

- **Quarterly monitoring**: elected monitors conduct sonar surveys each quarter and compile catch data from all trips to estimate total stock.
- **Catch logging**: every trip’s catch is recorded on the communal ledger.
- **Excess handling**: if a fisher exceeds the 10 % limit, the excess kilograms and a 10 % tax (1 kg = 1 credit) are automatically moved to the reserve account.
- **Fines**: monitors levy a fine of **20 community credits** for any violation of the 10 % limit.
- **Moratorium trigger**: when survey data shows stock < 25 % of estimated capacity, monitors impose a moratorium.
- **Moratorium release**: the moratorium is lifted after two back‑to‑back quarterly surveys show stock ≥ 25 % and no dip below that level in either survey.
- **Governance**:
  - A rotating **committee of five** members (one‑year term, renewable once) elected by simple majority at the monthly meeting.
  - quorum of **three** members required for any vote.
  - The committee meets monthly to review reserve balance, approve expenditures (simple majority of present members), and oversee lake restoration, shared gear, and emergency supplies.
- **Auditing**:
  - An **auditor** (one‑year term, elected by simple majority) with ≥ 3 years experience in public accounting, auditing, or fisheries management audits the ledger annually, posting findings on the ledger and presenting at the monthly committee meeting.
- **Community credit**: defined as one kilogram of fish; its monetary value is the current market price per kilogram as determined by the community’s monthly market survey.

**Fluents introduced**

| fluent name | represents |
|---|---|
| `catch_tax` | Amount of community credits collected from the 10 % catch‑tax each round.
| `excess_catch` | Kilograms of fish harvested above the 10 % per‑trip limit.
| `moratorium_active` | Boolean flag indicating whether a temporary fishing moratorium is currently in force.
| `monitor_fine` | Credits levied on a fisher for exceeding the 10 % limit.
| `stock_surplus` | Kilograms of fish above the 25 % regeneration threshold (used to determine moratorium lift).

**Norm implementation notes**

- Implement a `CatchLimitNorm` subclass in `norms/catch_limit.py` with `type_name = "catch_limit"`.
- In `evaluate`, enforce the 10 % per‑trip cap, calculate excess, apply `NormDecision.adjust` for the excess and tax, and `NormDecision.violation` when the 10 % limit is breached, attaching a `monitor_fine` note.
- Implement a `MoratoriumNorm` subclass in `norms/moratorium.py` with `type_name = "moratorium"`.
- Use `on_round_start` to check the latest quarterly survey (available via `context`), set `moratorium_active` fluent, and enforce a zero‑harvest policy while active.
- Use `on_round_end` to evaluate if two consecutive surveys have shown stock ≥ 25 % to lift the moratorium.
- Ensure both norms are listed in `state/config.json` under the `norms` array with appropriate `params` (e.g., `{ "type": "catch_limit" }`, `{ "type": "moratorium" }`).
- Update `state/institution.json` `norm_types` catalog to include the new `type_name`s.
- Add entries for the new fluents to `state/fluents_schema.md` as shown above.

---

*This specification follows the updated `norm.txt` for round 1 and provides the concrete policy, operational details, required fluents, and implementation guidance for norm‑implementers.*
