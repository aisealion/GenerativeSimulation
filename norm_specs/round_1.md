# Round 1 Norm Specification

**Policy (as written in `norm.txt`):**

Each fisher may take at most **10 kg** per trip; any excess over 10 kg is automatically deposited into a communal reserve, and **5 %** of the total haul must be deposited into that reserve and recorded in the communal ledger. The Reserve Officer—chosen by community vote among fishers who have completed at least three successful trips—will oversee deposits, lock the bin, and enforce bans for non‑compliance.

**Operationalization for the simulation:**

1. Before the harvest action, the fisher’s raw catch (`raw_kg`) is recorded.
2. The `ReserveNorm` (type `"reserve"`) executes during the norm evaluation phase:
   * Computes any excess over the **10 kg** cap.
   * Computes **5 %** of the total haul.
   * Deposits both amounts into the communal reserve.
   * Adjusts the fisher’s kept catch to `raw_kg - excess - 0.05 * raw_kg`.
   * Emits a note summarizing the deposits (e.g., "excess 2.30 kg deposited to reserve, 5 % (0.65 kg) deposited to reserve").
3. The simulation records these deposits implicitly via the adjusted kept kilograms. The Reserve Officer logic (selection, auditing, bans) is outside the scope of this norm plugin and is handled by other parts of the system.

**Configuration entry (added to `state/config.json`):**

```json
{"type": "reserve", "id": "reserve"}
```

This entry enables the new norm for the current round.
