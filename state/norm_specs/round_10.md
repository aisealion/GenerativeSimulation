# Round 10 Norm Specification

**Policy (as written in `norm.txt`):**

For round 10, the community decides that each fisher may take up to **15 kg** per trip, but any amount exceeding **12 kg** must be deposited into the communal reserve. Additionally, each fisher must contribute **2 kg** of their catch to a shared emergency fund, regardless of total haul. The reserve manager, elected by majority vote among fishers who have completed at least five trips, oversees deposits, audits the fund, and can enforce penalties for non‑compliance.

**Operationalization for the simulation:**

1. After the harvest action, the fisher’s raw catch (`raw_kg`) is recorded.
2. The `ReserveNorm` (type `"reserve"`) runs during the norm evaluation phase:
   * Calculates any excess over the **12 kg** cap.
   * Deposits the excess into the communal reserve.
3. The `EmergencyFundNorm` (type `"emergency_fund"`) then runs:
   * Subtracts a fixed **2 kg** from the fisher’s remaining keep (or the full catch if less than 2 kg).
   * Deposits this amount into the emergency fund.
4. The fisher’s final kept catch is adjusted accordingly.
5. Notes are emitted summarizing deposits, e.g., "excess 3 kg deposited to reserve, 2 kg to emergency fund".

**Configuration entry (add to `state/config.json`):**

```json
[
  {"type": "reserve", "id": "reserve"},
  {"type": "emergency_fund", "id": "emergencyFund"}
]
```

This entry enables both norms for the current round.
