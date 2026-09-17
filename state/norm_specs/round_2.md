# Round 2 Specification

This round implements the policy and operationalization from `norm.txt`.

| Requirement | Shape | Level | Owner | Verification |
|---|---|---|---|---|
| Council composition: elected annually; includes clerk chosen by majority vote | role_creation | 2 | actions/rules/harvest/percentage_cap.py (percentage_cap) | NOT_IMPLEMENTED_THIS_ROUND |
| Ledger holds lake stock and daily net catches; updated after each trip | object_type | 2 | NOT_IMPLEMENTED_THIS_ROUND (ledger object) | NOT_IMPLEMENTED_THIS_ROUND |
| Trip logging: fisher submits catch log | action | 2 | NOT_IMPLEMENTED_THIS_ROUND (trip_logging action) | NOT_IMPLEMENTED_THIS_ROUND |
| Clerk verification of 5% cap, trimming, 10% penalty | catch_constraint | 3 | actions/rules/harvest/percentage_cap.py (percentage_cap) | NOT_IMPLEMENTED_THIS_ROUND |
| Minimum catch enforcement (≥1 kg) | catch_constraint | 3 | actions/rules/harvest/percentage_cap.py (percentage_cap) | NOT_IMPLEMENTED_THIS_ROUND |
| Stock update after accepted trip | state_update | 1 | actions/handlers/harvest.py (harvest handler) | NOT_IMPLEMENTED_THIS_ROUND |
| End‑of‑day community daily cap (30%) and surplus distribution | catch_constraint | 3 | actions/rules/harvest/daily_cap.py (daily_cap) | NOT_IMPLEMENTED_THIS_ROUND |
| Repeat offender ban (exceed 5% twice) | sanction_rule | 3 | actions/rules/harvest/repeat_offender_ban.py (repeat_offender_ban) | NOT_IMPLEMENTED_THIS_ROUND |
| Reserves tracking per fisher | object_type | 2 | NOT_IMPLEMENTED_THIS_ROUND (reserve object) | NOT_IMPLEMENTED_THIS_ROUND |
| Enforcement logging of council actions, penalties, bans | action | 2 | NOT_IMPLEMENTED_THIS_ROUND (enforcement action) | NOT_IMPLEMENTED_THIS_ROUND |
