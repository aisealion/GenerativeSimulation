# norms/

Every per-agent constraint on harvesting — a cap, a reserve, a ban — is a
plugin here, not code inlined into `phases/harvest.py`. `phases/harvest.py`
implements *how harvesting happens* (physics); a norm implements *a
constraint around it*. A new adopted norm becomes either a config change
activating an existing plugin, or a new small plugin file — never a rewrite
of `phases/harvest.py` itself, which no longer contains any norm-specific
logic at all.

## How it's wired together

Every round, `HarvestPhase.run()` builds one `HarvestContext`
(`engine/norms/context.py`) and one `NormEngine`
(`engine/norms/engine.py`) from `state["config"]["norms"]`, then for each
alive agent:

1. `norm_engine.is_eligible(context, agent_id)` — if any norm says no (a
   live ban), the agent's LLM call is skipped entirely this round.
2. The agent's effort is turned into a raw kg catch via
   `engine.physics.catch_from_effort()` — fixed physics, not a norm's
   concern.
3. `norm_engine.apply(context, agent_id, raw_kg)` threads that raw catch
   through every active norm's `evaluate()`, **in the order they appear in
   `state["config"]["norms"]`** — each norm sees what the previous one
   already decided. Order matters: see the `reserve` example below.

A norm can also contribute an agent-facing sentence via `describe()`
(joined into the harvest prompt's `{constraints_line}`), and can hold
state across rounds via `context.norm_state(self.key)` (persisted in
`state/runtime.json` under `runtime["norms"][key]`) or just for the current
round via `context.round_scratch(self.key)` (never persisted — useful for
a running per-round tally).

See `engine/norms/base.py`'s `Norm` class for the full hook contract
(`is_eligible`, `describe`, `on_round_start`, `evaluate`,
`on_agent_settled`, `on_round_end`) — that file is off-limits to edit, but
its docstrings are the actual spec for what each hook does and when it's
called.

## Norm types available today

- **`catch_limit`** — a flat or percentage-of-stock per-trip kg ceiling,
  with an optional per-agent override.
- **`reserve`** — a shared reserve that banks whatever an earlier norm in
  the list trimmed off an agent's catch, and lets a low-catcher withdraw
  from it.
- **`violation_ban`** — a multi-trip fishing ban triggered by a matching
  sanction from another norm in the chain.
- **`community_cap`** — a round-level cap (or "replenish if over X%")
  independent of any one agent's own limit.

## Worked example

A norm like "each fisher may keep up to 12kg per trip; anything beyond
that goes into a shared reserve; a fisher who brings in less than 5kg may
draw up to 4kg from the reserve to top up; two violations of the cap in a
row means a two-trip ban" is pure configuration — no new plugin file
needed:

```json
{
  "norms": [
    {"type": "catch_limit", "limit_kg": 12},
    {"type": "reserve", "shortfall_threshold_kg": 5, "max_withdrawal_kg": 4},
    {"type": "violation_ban", "trigger_sanction": "over_cap", "trips": 2}
  ]
}
```

Note the order: `reserve` comes *after* `catch_limit` specifically because
it deposits whatever the previous norm in the chain already trimmed off
(`raw_kg - proposed_kg`) — reversing the order would mean `reserve` runs
before there's anything to deposit, and the reserve would never grow.

If a genuinely new *shape* of constraint is needed — nothing above fits,
even with different parameters — add a new `norms/{name}.py` file
subclassing `Norm` with a unique `type_name`; it's picked up automatically
by `engine/norms/registry.py`'s auto-discovery, no registry edit required.
