# Round 11 Norm Specification

**Policy**
- Each fisher may take at most **2 kg** per trip.
- **35 %** of each catch must be deposited into a communal reserve.
- The communal reserve must always hold at least **35 %** of the lake’s current biomass.
- Any shortfall in the required deposit or any excess catch beyond the 2 kg cap incurs an immediate fine collected by the treasurer.
- The treasurer suspends any fisherman who fails to pay the fine until the fine is settled.
- Fishing is suspended community‑wide if the reserve falls below the 35 % threshold; fishing resumes only after the reserve is replenished through fines or voluntary contributions.

**Operationalization**
1. After each trip the fisher logs the amount kept and the 35 % deposit.
2. The elected treasurer (per season) tallies all deposits, verifies that no catch exceeds the 2 kg cap, and records any fine equal to the missing deposit or excess catch. The fine is added to the communal reserve immediately.
3. The treasurer computes the lake’s biomass by subtracting the total catch from the previous round’s biomass and adding any voluntary contributions; the communal reserve must remain at least 35 % of that biomass.
4. If the reserve dips below the threshold, the treasurer notifies the community and fishing is suspended. The reserve must be brought back above the threshold before fishing can resume.
5. Suspended fishers may resume once their fine is paid and the treasurer confirms compliance.

**Parameters**
- `CAP_KG = 2.0`
- `DEPOSIT_PCT = 0.35`
- `RESERVE_MIN_PCT = 0.35`
- `FINE_RATE = 1.0` (fine equals the exact shortfall or excess amount in kg)

**State Keys**
- Persistent reserve balance stored in `context.norm_state(self.key)['reserve_kg']`.
- Per‑round deposits recorded in `context.round_scratch(self.key)['deposits']`.
- Per‑round fines recorded in `context.round_scratch(self.key)['fines']`.

**Norm Hooks**
- `evaluate` enforces the cap, calculates required deposit, issues fines when needed, and records deposits/fines.
- `on_round_end` aggregates deposits and fines into the persistent reserve.
- `is_eligible` may be used to block agents with unpaid fines (not implemented here).
