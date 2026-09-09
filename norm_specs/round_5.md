# Round 5 Norm Specification

**Policy (as written in `norm.txt`):**

Each fisher may take up to **12 kg** per trip and must set aside **1 kg** to a community pot; if lake stock falls below **100 kg** the catch limit is reduced to **8 kg**. The pot‑keeper is elected monthly by secret ballot, records contributions, and allocates **60 %** of the pot to maintenance and **40 %** to emergency aid, with a **20 %** reallocation allowed in a serious emergency after Maintenance‑Aid Committee approval.

**Operationalization for the simulation:**

1. After the harvest action, the fisher’s raw catch (`raw_kg`) is recorded.
2. The `CommunityPotNorm` (type `"pot"`) executes during the norm evaluation phase (as in Round 2) and deposits **1 kg** (or the full catch if less than 1 kg) into the communal pot, adjusting the kept catch accordingly.
3. The `CatchLimitNorm` (type `"catch_limit"`) then runs:
   * It reads the lake’s current stock via `context.stock_before`.
   * If the stock is **≥ 100 kg**, the per‑trip cap is **12 kg**; otherwise the cap is **8 kg**.
   * If the fisher’s proposed keep (`proposed_kg`) exceeds the applicable cap, the norm reduces it to the cap and emits a note, e.g., "catch limited to 8 kg due to low lake stock".
4. The two norms are ordered in `state/config.json` so that the pot contribution happens first, then the catch‑limit adjustment.
5. The simulation records the pot balance implicitly via the adjusted kept kilograms. The pot‑keeper election, ledger, and allocation logic are modelled elsewhere and are out of scope for this norm plugin.

**Configuration entry (add to `state/config.json`):**

```json
[  
  {"type": "pot", "id": "communityPot"},
  {"type": "catch_limit", "id": "catchLimit"}
]
```

This entry enables both norms for the current round.
