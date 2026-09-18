# Round 2 Specification

Implemented the 15 kg per‑trip catch cap and associated violation handling as per norm.txt.

- Updated `CapRule` parameters in `state/config.json` to enforce a 15 kg cap.
- Added `ViolationRule` logic to track violations, impose a one‑month revocation after three offenses, and require a 5 kg contribution to the communal reserve.
- Council meeting action (`council_meeting`) remains as the enforcement review point, with no additional rule logic needed for this round.

All operationalization clauses are now enforced by the institution.
