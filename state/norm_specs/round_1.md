# Round 1 Specification

This round implements the weight cap policy and associated infractions.

| Requirement | Shape | Level | Owner | Verification |
|---|---|---|---|---|
| Fisher weight per trip ≤ 10 kg; excess released; infraction recorded; warning on second infraction; revocation on third requires community vote | catch_constraint | 3 | actions/rules/harvest/weight_cap.py (weight_cap) | tests/norm_checks/test_round_1_weight_cap.py |
| Revocation of fishing rights after third infraction (vote) | sanction_rule | NOT_IMPLEMENTED_THIS_ROUND | NOT_IMPLEMENTED_THIS_ROUND (reason: no rule implemented to trigger vote) | NOT_IMPLEMENTED_THIS_ROUND |
