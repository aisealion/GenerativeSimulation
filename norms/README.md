# norms/

Every per-agent constraint on harvesting — a cap, a reserve, a ban — is a
plugin here, not code inlined into `phases/harvest.py`. `phases/harvest.py`
implements *how harvesting happens* (physics); a norm implements *a
constraint around it*. A new adopted norm becomes either a config change
activating an *already-created* plugin from an earlier round, or a new
small plugin file — never a rewrite of `phases/harvest.py` itself, which
no longer contains any norm-specific logic at all.

**This directory ships empty of plugins by design** — no seed/example
`Norm` implementations, on purpose (removed 2026-09-04; see CLAUDE.md).
Round 1 must always operationalize its adopted norm from scratch: a
pre-built cap/reserve/ban plugin sitting here from the start would let the
norm-implementer just tune parameters on an already-correct
implementation instead of actually writing one, which defeats the point
of studying whether it can. A later round's plugin stays here and becomes
legitimately reusable via config alone by a subsequent round with a
similar-shaped norm — that reuse path is real and intended, it just never
starts pre-populated.

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
   already decided. Order matters: see the worked example below.

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

## Worked example (hypothetical — illustrates the pattern, not a real plugin)

A norm like "each fisher may keep up to 12kg per trip; anything beyond
that goes into a shared reserve; a fisher who brings in less than 5kg may
draw up to 4kg from the reserve to top up; two violations of the cap in a
row means a two-trip ban" would, if these three plugin *shapes* already
existed from an earlier round, become pure configuration — no new plugin
file needed for a round that just wants different numbers on an
already-existing shape:

```json
{
  "norms": [
    {"type": "example_cap", "limit_kg": 12},
    {"type": "example_reserve", "shortfall_threshold_kg": 5, "max_withdrawal_kg": 4},
    {"type": "example_ban", "trigger_sanction": "over_cap", "trips": 2}
  ]
}
```

Note the order: a reserve-shaped plugin must come *after* a cap-shaped one
specifically because it deposits whatever the previous norm in the chain
already trimmed off (`raw_kg - proposed_kg`) — reversing the order would
mean it runs before there's anything to deposit, and the reserve would
never grow. This ordering rule is general — it applies to any two plugins
in a deposit/withdraw relationship, not specifically to plugins named
`example_cap`/`example_reserve` (which don't exist; name your own
descriptively for what they actually do).

Since nothing exists here by default (see above), the very first norm any
round adopts is always genuinely new: add a `norms/{name}.py` file
subclassing `Norm` with a unique `type_name`; it's picked up automatically
by `engine/norms/registry.py`'s auto-discovery, no registry edit required.
A *later* round whose norm matches an *already-created* plugin's shape,
just with different numbers, can then configure it directly instead of
writing another one.

## How a norm gets verified before it's committed

The norm-implementer writes a formal requirement list to
`state/norm_specs/round_{N}.md` *before* touching any code (its own PHASE
1), classifying each requirement's clarity and resolving anything
ambiguous or incomplete via a short dialogue with the fisher who proposed
the rule. Once code exists, a separate `norm-evaluator` subagent — with no
access to `norms/` or `prompts/`, only to its own `tests/norm_evaluation/`
— writes and runs independent tests against that spec and classifies each
requirement as compliant, an implementation error, or a remaining spec gap.
See `.opencode/agent/norm-evaluator.md` for the full contract, and
`CLAUDE.md`'s "Norm-evaluator" entry for why this is a second agent rather
than another self-check inside the norm-implementer.
