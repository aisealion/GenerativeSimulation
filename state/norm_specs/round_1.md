# Norm Specification – Round 1

**Policy**
Each fisher may take up to **5 kg** per trip, but the community’s total monthly harvest may not exceed **10 %** of the current lake stock. The council calculates the monthly cap and enforces it. Any catch beyond the per‑trip limit or the monthly cap must be returned to the lake or logged for the next month according to the council’s decision.

**Operationalization**
1. **Council Composition** – A seasonal council elected by consensus, consisting of senior fishers, the shared‑ledger keeper, and a lake‑stock sampling overseer.
2. **Monthly Stock Calculation** – At the start of each month the council:
   - Takes the previous month’s stock estimate.
   - Adds a fixed growth factor of approximately **5 %** of that estimate.
   - Subtracts the total harvest recorded in the ledger.
   - The resulting estimate defines the **10 %** harvest cap for the month.
3. **Cap Enforcement** –
   - Each fisher logs a maximum of **5 kg** per trip.
   - Before setting out, a fisher checks the shared ledger; if the remaining allowable catch for the month is less than 5 kg, the fisher may only take that amount.
   - If a trip would push the cumulative monthly total over the cap, the fisher stops once the cap is reached, returning any excess to the lake or logging it as a credit for the next month.
4. **Ledger Record** – Every trip’s actual catch is recorded in the shared ledger immediately after landing.
5. **Temporary Ban** – If a fisher violates the per‑trip limit or the monthly cap, the council may impose a temporary ban lasting until the next monthly reset (i.e., until the new lake‑stock estimate and cap are calculated).
6. **Personal Reserve** – Each fisher must maintain a **1 kg** reserve per trip. The council monitors individual reserves and can suspend fishing if a fisher’s reserve falls below zero.
7. **Compliance Review** – The council reviews reported violations, determines the appropriate sanction (return, credit, or ban), and publishes the decision in the ledger.
8. **Renewal** – At the monthly reset, all bans are lifted and the cap is recalculated, allowing fishers to resume under the new limits.

*This specification corresponds to round 1 of the simulation and should be referenced by the norm engine when loading round‑specific configurations.*