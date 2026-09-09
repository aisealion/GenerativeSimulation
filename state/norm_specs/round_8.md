# Round 8 Norm Specification

**Policy (as written in `norm.txt`):**

Each fisher may take up to **12 kg** per trip, and the lake must retain at least **25 %** of its pre‑trip stock after each fishing round.

**Operationalization for the simulation:**

1. **Pre‑trip stock recording** – At the start of the round the first fisher records the lake’s total weight (`pre_stock_kg`) in the communal ledger.
2. **Catch capture** – Each fisher’s raw catch (`raw_kg`) is recorded when the `harvest` action is invoked.
3. **Per‑fisher cap** – The `CatchLimitNorm` (type `"catch_limit"`) runs during the norm‑evaluation phase:
   * If `raw_kg` ≤ 12 kg, the fisher keeps the full amount.
   * If `raw_kg` > 12 kg, the excess (`over_kg = raw_kg - 12`) is recorded as **over‑catch**, the fisher’s kept catch is reduced to 12 kg, and a note is emitted (e.g., "catch limited to 12 kg; 2 kg over‑catch recorded").
4. **Stock‑retention check** – After all harvest actions have been processed, the `StockRetentionNorm` (type `"stock_retention"`) computes the total harvested kilograms (`total_harvested`).
   * `remaining_stock = pre_stock_kg - total_harvested`
   * The required minimum is `min_stock = 0.25 * pre_stock_kg`.
   * If `remaining_stock < min_stock`, the shortfall (`shortfall_kg = min_stock - remaining_stock`) is multiplied by **20 % of the market value per kg** and added to the debt of the fisher(s) responsible for the shortfall. Responsibility is allocated proportionally to each fisher’s over‑catch amount.
5. **Fine for over‑catch** – For every kilogram recorded as over‑catch, a fine of **20 % of the current market value per kg** is added to that fisher’s debt.
6. **Debt handling** – Debt balances are stored per fisher in the ledger.
   * Unpaid debt at the end of the round triggers a **one‑round fishing ban** for that fisher.
   * While the debt remains, the fisher’s future catch allocation is reduced each round by `debt / market_value_kg` kilograms.
7. **Market‑value calculation** – `market_value_kg` is the average price per kilogram earned in the previous two rounds; if no sales occurred, a council‑set base rate is used.
8. **Audit & appeal** – All ledger entries are signed and timestamped. Appeals are processed by the fishing council using the ledger as evidence.

**Configuration entry (add to `state/config.json`):**

```json
[
  {"type": "catch_limit", "id": "catchLimit"},
  {"type": "stock_retention", "id": "stockRetention"}
]
```

These entries activate the two norm plugins for round 8. The configuration list should replace the empty array in `state/config.json` for this round.
