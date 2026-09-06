# Phase 1 specification for round 7

This specification documents the implementation of the norm for round 7 as described in `norm.txt`. The norm enforces a **12 kg per‑trip cap**, deposits any excess catch into a communal reserve, and at month‑end splits the reserve equally among the ten fishers, crediting each fisher’s monthly allowance. A fisher who fails to release excess fish forfeits his share of that month’s reserve and is barred from fishing the next month until he complies.

## Norm plugin
- File: `norms/cap_and_reserve.py`
- Class: `CapAndReserveNorm` (subclass of `engine.norms.base.Norm`)
- `type_name = "cap_and_reserve"`
- Implements:
  - `is_eligible` – checks ban counter stored in `context.norm_state(self.key)['banned_until']`.
  - `on_round_start` – decrements ban counters each round.
  - `evaluate` – if `raw_kg` ≤ 12 kg, allow catch; otherwise add full `raw_kg` to communal reserve (`norm_state[self.RESERVE_KEY]`) and set a 1‑month ban, returning a `NormDecision.violation` with `kept_kg=0.0`.
  - `describe` – short user‑facing description of the cap and reserve split.
  - `on_month_end` – called once per month to split the reserve evenly among the ten fishers, credit each fisher’s allowance in the ledger, and reset the reserve to zero.

## Configuration
Add the norm to the simulation config (e.g. `state/config.json`):
```json
{
  "norms": [
    {"type": "cap_and_reserve"}
  ]
}
```
The norm requires no additional parameters.

## Persistent state keys (via `context.norm_state(self.key)`) 
- `reserve_kg` – total kg accumulated in the communal reserve for the current month.
- `banned_until` – mapping of `agent_id` → remaining ban rounds.

## Expected behavior
1. Agents catching ≤ 12 kg keep their catch.
2. Agents catching > 12 kg forfeit the entire catch to the communal reserve, receive a note explaining the forfeiture, and are banned for the next month.
3. At month‑end the reserve is divided evenly among the ten agents; each agent’s monthly allowance is increased by the split amount.
4. Agents who failed to release excess fish do **not** receive a share of that month’s reserve and remain banned until they comply.
5. Bans decrement each round and expire automatically after the required month.
6. The communal reserve persists only within the month via `norm_state` and is reset after splitting.

## PHASE 1 spec file location
Write this specification to `state/norm_specs/round_7.md`.
