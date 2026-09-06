# Phase 1 specification for round 6

This specification documents the implementation of the norm for round 6 as described in `norm.txt`. The norm enforces a **30 kg per‑trip cap**, adds any excess catch to a communal reserve, and imposes a one‑month fishing ban on agents who exceed the cap.

## Norm plugin
- File: `norms/cap_and_reserve.py`
- Class: `CapAndReserveNorm` (subclass of `engine.norms.base.Norm`)
- `type_name = "cap_and_reserve"`
- Implements:
  - `is_eligible` – checks ban counter stored in `context.norm_state(self.key)['banned_until']`.
  - `on_round_start` – decrements ban counters each round.
  - `evaluate` – if `raw_kg` ≤ 30 kg, allow catch; otherwise add full `raw_kg` to communal reserve (`norm_state[self.RESERVE_KEY]`) and set a 1‑month ban, returning a `NormDecision.violation` with `kept_kg=0.0`.
  - `describe` – short user‑facing description of the cap.
  - `on_round_end` – placeholder (no‑op).

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
- `reserve_kg` – total kg accumulated in the communal reserve.
- `banned_until` – mapping of `agent_id` → remaining ban rounds.

## Expected behavior
1. Agents catching ≤ 30 kg keep their catch.
2. Agents catching > 30 kg forfeit the entire catch to the communal reserve, receive a note explaining the forfeiture, and are banned for the next round.
3. Bans decrement each round and expire automatically.
4. The communal reserve persists across rounds via `norm_state`.

## PHASE 1 spec file location
Write this specification to `state/norm_specs/round_6.md`.
