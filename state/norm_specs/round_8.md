# Round 8 Norm Specification

**Policy**
- Each fisher may catch up to **4 kg** per trip.
- The fisher **must keep at least 1 kg** for personal use on every trip.
- The **community’s total monthly catch** must not exceed **25 % of the lake’s stock at the start of the month**.

**Operationalization**
1. **Per‑trip enforcement**
   - If a trip’s raw catch exceeds 4 kg, it is trimmed to 4 kg.
   - If the raw catch is less than 1 kg, the trip is a violation; the fisher receives a sanction (e.g., a ban) and keeps nothing.
   - Otherwise, the fisher keeps exactly 1 kg; the remainder is deposited into the communal reserve.
2. **Monthly accounting**
   - After each trip, the raw catch (post‑trim) is recorded in `context.round_scratch` under the norm’s key.
   - At month’s end, the total catch per fisher is summed.
   - If a fisher’s total exceeds **25 % of the lake’s starting stock**, the excess is returned and **double‑deposited** to the communal reserve.
   - A sanction record is stored in the norm state for any fisher who exceeds the monthly limit.
3. **Sanctions**
   - Violation of the personal‑keep rule (catch < 1 kg) triggers a `ban` sanction.
   - Exceeding the monthly limit records an `excess` and `penalty_deposited` entry in the norm state.

**Implementation notes**
- Implemented as `MonthlyLimit25Norm` in `norms/monthly_limit_25_norm.py`.
- Uses `NormDecision.adjust` for normal trips, `NormDecision.violation` for personal‑keep violations.
- Updates the communal reserve via `context.norm_state(self.key)["reserve_kg"]`.
- Stores per‑agent monthly totals in `context.round_scratch(self.key)["catch_by_agent"]`.
- End‑of‑month logic in `on_round_end` enforces the 25 % cap and applies penalties.
