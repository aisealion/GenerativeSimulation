# Action contract — `state/actions/{name}.json` + `actions/handlers/{name}.py`

Read this before touching `new_action.md` (the recipe) for real, or before
judging a new action "too much infrastructure."

## `ActionSpec` (`state/actions/{name}.json`)

Fields: `name` (matches the filename stem and the `state/institution.json`
key), `description`, `scheduling` (`gate`: `"true"`/`"false"`/
`"holdsAt(<fluent>)"`, plus `after`/`before` naming another action by
name — `state/schedule.json` is *compiled* from these, never hand-edited),
`participation` (`{"policy": "all_alive_fishers"}` by default, or
`{"policy": "role_holders", "role": "<name>"}`), `roles.actor_role` (the
role this action structurally requires, or `null`), `execution.handler`
(`"generic_agent_decision"` — Level 2, or a filename stem under
`actions/handlers/`), and `prompt.template` (a format-string body,
filled by `engine.llm_agents.render_action()` from whatever fields the
handler shape resolves — **no separate prompt file for a normal action**;
`actions/prompts/` only holds content not owned by any one action's own
spec — a sub-step of a multi-call action, or a standalone tool like
`engine/clarify_norm.py`; see `actions/prompts/README.md`).

## Level 2 — `generic_agent_decision`, zero Python

Set `execution.handler: "generic_agent_decision"` for "ask one question
per participating alive agent, record the answer verbatim (optionally
renaming fields)" — the common shape for a simple reporting/estimating
requirement with no further institutional effect this round. Declare
`prompt.fields` (each entry `{"from": "state", "path":
"runtime.stock_kg"}` / `{"from": "object", "object_id": ..., "field":
...}` / `{"literal": ...}`) and optionally `outputs.fields` to rename
specific response keys (omit it to copy the response verbatim). Read
`engine/institution/builtin_handlers.py` in full before using this — it's
deliberately small and does **not** support a role grant, an
institutional fact, custom eligibility, or reading another participant's
own answer. Eligibility/after-agent rule hooks are already wired in
automatically.

## Level 4 — a custom handler

Write `actions/handlers/{name}.py` the moment the action needs anything
Level 2 doesn't support: `def run(ctx) -> round_record`.

`ctx` is an `engine.institution.context.ActionContext`:

- `.state` — the full round-state dict.
- `.round_number`
- `.participants` — already resolved per the spec's `participation`
  policy.
- `.agents.call(agent_id, **fields)` — calls the fisher agent under this
  action's own name.
- `.events.emit(...)` — narrates an institutional occurrence (see
  `object-contract.md`).
- `.objects` — an `ObjectRuntime` (see `object-contract.md`).
- `.rules` — this action's own `RuleSet` (see `rule-contract.md`). Every
  handler in this project — including the generic Level-2 path — calls
  `ctx.rules.is_eligible(...)`/`ctx.rules.apply_after_agent(...)`/
  `ctx.rules.settle_agent(...)` around its own per-agent loop, and
  `ActionRuntime` itself calls `ctx.rules.before_action(...)`/
  `after_action(...)` around the handler call generically — this is what
  makes every action, not just harvest, a real place for a rule to
  attach.

Optionally exposes `memory_writes(state, round_record)`, same contract as
before.

If the action still needs only one `ctx.agents.call(...)` per agent —
just with fields/output shaping Level 2 can't express (`propose.py`'s
cross-agent aggregation, `vote.py`'s tally) — use
`engine.institution.agent_loop.per_agent_decision(ctx, build_fields,
build_record)` for the loop itself, the same helper `harvest.py`/
`propose.py`/`vote.py` all use, rather than hand-rolling the
eligibility-check/call/rule-patch sequence again. Write the loop by hand
only when the action genuinely needs more than one call per agent
(`critique.py`'s bounded dialogue) or no call at all. `propose.py` is the
smallest real custom example using the helper (needs a handler only
because it aggregates every *other* participant's last-round catch).

Any new runtime state either shape needs is lazily initialized inside the
handler's own `run()` (`runtime.setdefault(...)`) or needs none (generic
path) — never pre-seed it in `state/runtime.json`.

## Registration

`state/institution.json`: add `"{name}": {"spec": "state/actions/{name}.json",
"protected": false}`, a `roles` entry if this introduced a new role
(`{"exclusive": bool, "description": ..., "introduced_round": N}`), and
any new state fields under `"state"`. Never touch `state/schedule.json`
directly — it recompiles automatically the moment your changes are read.

## Protection

The five pre-existing actions and their handlers, plus every action any
earlier round has added, are permanently off-limits to editing — see
`architecture.md`. If a rule needs to change an *existing* action's own
decision — not add a new one alongside it — stop and report; that's a
human-scoped change, same as touching `engine/institution/` directly.
