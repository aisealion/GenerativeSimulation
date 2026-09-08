## Round 1 Norm Specification

**Policy**: No fisher may net more than **20 kg** per trip. Any excess must be returned on the spot, a **1 kg** fine is added to the communal reserve, and the fisher receives a **one‑week ban**. All actions are logged in the shared ledger and overseen by a rotating steward.

**Operationalization**
1. A *trip* starts when a fisher leaves the dock and ends when they return to unload.
2. Upon docking, the fisher records the total catch weight (kg) in the communal ledger with their name, date, and weight.
3. If the recorded weight exceeds **20 kg**, the fisher must immediately return the excess weight to the lake.
4. The current steward (rotating monthly) verifies the return by weighing the returned fish and records the returned weight in the ledger, then signs the entry.
5. The ledger adds **1 kg** to `communal_reserve_kg` and increments the fisher’s fine column by **1 kg**.
6. The ledger entry shows the fine, returned weight, and steward’s signature.
7. The steward reviews the ledger daily; any fisher who logs > 20 kg without returning excess is flagged for a **one‑week ban**.
8. The ban entry records fisher name, start date (current date), and end date (start + 7 days) and is displayed in the ledger.
9. During the ban period the fisher’s entries are locked; they cannot log any catch.
10. When the ban expires, the steward clears the ban status from the ledger.
11. All entries are visible to the community; `communal_reserve_kg` reflects total fines collected.
12. The steward rotation ensures no single fisher holds audit power and the process remains transparent.
