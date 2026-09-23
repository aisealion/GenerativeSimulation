# State files — what each one is for, who owns what

## Norm-engineer-writable

- **`state/config.json`** — `"rules"`: a dict keyed by action name, each
  value a list of `{"type": ..., "id"?: ..., "lifecycle"?: {...},
  ...params}` objects. **Order within one action's own list is
  enforcement order** (a reserve-shaped rule after any cap-shaped rule it
  draws from; a rule on a *different* action has no ordering relationship
  to this one). Activating/deactivating a type here also means opening/
  closing its `rule_active` fluent (`rule-contract.md`).
- **`state/institution.json`** — the one place "what actions, roles, rule
  types, and object types currently exist, structurally" lives:
  `{"version", "updated_at_round", "actions": {name: {"spec",
  "protected"}}, "roles": {name: {"exclusive", "description",
  "introduced_round"}}, "rule_types": {name: {"description", "owner"}},
  "object_types": {name: {"description", "owner"}}, "state": {...}}`.
  `rule_types`' `owner` path encodes which action a type belongs to
  (`actions/rules/harvest/trip_cap.py`) — a `type_name` is only unique
  within its own action's subdirectory. **`version`/`updated_at_round`
  are orchestrator-owned — never edit them.** After a compliant round,
  `record_institution_changes()` diffs your edit, bumps `version`, and
  appends to `state/institution_history.jsonl` automatically — you'll
  never see the bump during your own session. Update the rest the moment
  you add an action, a genuinely new rule/object type, a new role, or a
  new state field — a drift check discards the round if this file and
  reality disagree in either direction.
- **`state/fluents.json`** — schema yours (via `state/fluents_schema.md`).
  Interval facts only (roles, bans, `rule_active`) — content is written
  by simulation code (`set_fact()`/`end_fact()`), not hand-edited.
- **`state/fluents_schema.md`** — canonical fluent-name registry, one
  line per name. Check before naming a new one; reuse an existing name
  for an existing concept.
- **`state/events.json`** — point-in-time occurrences. Content populated
  by `ctx.events.emit(...)`/`ObjectRuntime`'s `narration` kwarg at run
  time, same relationship you have with `state/fluents.json`'s content.
- **`state/actions/{name}.json`** — allowlisted for *adding* a new file
  only; the five pre-existing specs (and any action an earlier round of
  yours added) are permanently off-limits (`architecture.md`).
- **`state/object_types/{type}.json`**, **`state/objects.json`** — see
  `object-contract.md`.
- **`state/norm_specs/round_{N}.md`** — written by `norm-finalizer`, not
  you directly, after every requirement is actually implemented — you
  dispatch it with your full classification; it verifies and writes.
  Must land at exactly this path, under `state/` — two real rounds wrote
  to `norm_specs/round_{N}.md` at the repo root instead (dropping the
  `state/` prefix), which the orchestrator's check can't find, discarding
  otherwise-real work over a path typo.
- **`tests/norm_checks/round_{N}/`** — **not yours** — `norm-architect`'s
  exclusive surface, written before you ever run (naming convention in
  its own README). You read every test there before writing any code, but
  cannot edit it (denied by permission) — it's the pre-written target
  your implementation must satisfy, not something you author or adjust.
- **`prompts/role_directives/{role}.md`**, action-spec `prompt.template` —
  see `action-contract.md`/`role-contract.md`.
- **`prompts/phrasing_map.json`** — the fourth-wall boundary: no internal
  key names, code identifiers, or "mechanism"/"norm"/"fluent"/"penalty
  function" ever in rendered text, only their mapped phrasing.
- **`engine/simulate.py`** — allowed but last resort only: reserve for
  genuinely orchestration-level changes (a new scheduling primitive, a
  cross-action safety check), never a convenient place to patch a bug
  that belongs in a rule's own logic.

## Read-only to you

- **`state/schedule.json`** — compiled every round from
  `state/institution.json` + each spec's own `scheduling`. Denied by
  permission outright.
- **`state/runtime.json`** — simulation-owned. Never seed or initialize a
  value here, including `runtime["rules"][key]` or
  `runtime["objects"][id]["fields"]` — a rule's/object's own persistent
  state is written by simulation code at run time, never pre-seeded.
- **`tests/regression/`** — fixed, human-owned. Never weaken or delete a
  test to make it pass; say so explicitly and stop if you believe one is
  wrong.
- **norm-auditor writes nothing at all** (2026-09-23) — it's a plain,
  tool-free completion call that reads norm.txt and your diff directly
  and reports a verdict as text; it never runs its own pytest suite
  against `tests/norm_checks/round_{N}/`. A NEEDS_REPAIR report from it
  is therefore always prose describing a specific gap (often
  under-enforcement — a weaker mechanism than the norm's own text
  demands, even though your existing tests still pass), never a failing
  test of its own to point at.
- **`prompts/persona_template.md`** — human-owned, essentially never
  yours.
- **`engine/institution/`**, **`engine/physics.py`**, **`roles/roles.py`**
  — the fixed generic kernel and physics. If a rule needs something this
  layer doesn't expose, that's out of scope — stop and report it.
- **`constants/agents.json`** — fixed roster, not yours.

## Operational infra — `read` denied by permission

`ops/`, `.git/`, `.codegraph/`, `.pytest_cache/`, `.venv-fishery/`, and
every package's own `__pycache__/`. None of it describes the institution.
