# Round 2 Norm Specification

**Policy (as written in `norm.txt`):**

Each fisher must set aside **1 kg** of their catch per trip for the community pot, retaining the remainder.

**Operationalization for the simulation:**

1. After the harvest action, the fisher’s raw catch (`raw_kg`) is recorded.
2. The `CommunityPotNorm` (type `"pot"`) executes during the norm evaluation phase:
   * Subtracts **1 kg** from the raw catch (or the full catch if `raw_kg < 1 kg`).
   * Deposits the subtracted kilogram into the communal pot.
   * Adjusts the fisher’s kept catch to `raw_kg - 1.0` (or `0` if the catch was less than 1 kg).
   * Emits a note summarizing the deposit, e.g., "1 kg deposited to community pot".
3. The simulation records the pot balance implicitly via the deposited kilograms. Enforcement actions (ledger signing, pot‑keeper verification, suspension) are modelled elsewhere in the system and are outside the scope of this norm plugin.

**Configuration entry (add to `state/config.json`):**

```json
{"type": "pot", "id": "communityPot"}
```

This entry enables the new norm for the current round.