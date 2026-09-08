# Round 34 Norm Specification

**Policy**
- Each fisher may take up to **80 %** of the lake’s current biomass per trip.
- **10 %** of each catch is deposited into the communal reserve.
- If the reserve falls below **5 kg**, the next trip’s maximum take is lowered by **20 %** (to 64 % of lake biomass) and stays reduced until the reserve reaches **10 kg**.
- Failure to deposit or exceeding the quota triggers a **0.01 kg fine** and a **0.01 kg restitution** to the reserve.

**Operationalization**
1. Before each trip, the fisher checks the current lake biomass **B** and communal reserve total **R**.
2. Allowed take **T**:
   - If **R ≥ 5 kg**, then **T = 0.8 × B**.
   - If **R < 5 kg**, then **T = 0.8 × B × 0.8 = 0.64 × B** (reduced quota).
3. After fishing, the fisher records the catch **C**.
4. If **C > T** or the fisher fails to deposit the required 10 % of **C**, a **0.01 kg fine** is applied and **0.01 kg** is added back to the reserve.
5. The required deposit (**0.1 × C**) is transferred to the communal reserve ledger.
6. The ledger is updated with the deposit (and any fine) and the new reserve total.
7. The **Reserve Keeper** (weekly rotating fisher with highest net catch) signs the ledger daily.
8. The **Community Council** meets each Friday to audit the ledger. If **R ≥ 10 kg**, the quota is lifted back to 80 % for the next trip. If **R < 5 kg**, the reduced quota remains until the reserve reaches 10 kg.
9. All fishers must check the posted reserve level before setting out.
10. Fines are paid from the fisher’s next trip’s catch or directly to the keeper if the catch is already deposited.

**State Persistence**
- Reserve balance is stored in `context.norm_state('round_34')['reserve_kg']`.
- Reduced quota flag is stored in `context.norm_state('round_34')['reduced']` (boolean).
- Fine accumulation can be tracked in `context.norm_state('round_34')['pending_fines']` if needed.

**Norm Hooks**
- `describe`: Returns a human‑readable description of the current quota and reserve status.
- `evaluate`: Enforces the quota, deposit requirement, and applies fines/restitution.
- `on_round_end`: Updates the communal reserve, lifts or applies quota reduction based on reserve thresholds.
