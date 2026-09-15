# Role contract — structure vs. current holder

`state/institution.json`'s `roles[name]` (`{"exclusive", "description",
"introduced_round"}`) and an action's own `roles.actor_role` describe
**structure only** — does this role exist, does it rotate, does this
action require it. **Never** who holds it right now, and never cache
that answer here (see `architecture.md`'s "roles: structure vs. current
holder").

## Finding out who holds a role right now

`roles.roles.current_holder(fluents, role_name, round_number)` — a live
lookup against `state/fluents.json`, called fresh every time it's needed
(most often from an action's own `prompt_fields()`/`prompt.fields`).
Never add anything like `"active_roles": {"recorder": "agent_1"}` to
`state/institution.json` — the moment rotation reassigns the role, that
cached value goes stale, and nothing would ever remember to update it
(`state/institution.json` only changes when the institution's *shape*
changes, not every round).

## Assigning a role

`roles/roles.py`'s primitives, never hand-mutated `state/fluents.json`:

- `assign_role(role_name, agent_id, fluents, round_number)` — for a role
  every eligible agent holds *simultaneously and independently*
  (`fisher`).
- **For an exclusive, rotating role (a recorder, steward, monitor),
  always pass `exclusive=True`**: `assign_role(role_name, agent_id,
  fluents, round_number, exclusive=True)`. The default `args=[agent_id]`
  **silently breaks rotation** — `set_fact()` only terminates a previous
  record when `(fluent_name, args)` matches exactly, and each new
  holder's `[agent_id]` differs from the last, so the old holder's record
  never closes. Confirmed directly: this leaves two "open" holders at
  once, and `current_holder()` returns whichever happens to appear first
  — silently wrong. `exclusive=True` forces a fixed, agent-independent
  `args=[]` so rotation actually closes the previous holder's record.
- `set_fact(fluents, name, args, holder, round_number, narration=None,
  visibility="agent_only", event_type=...)` — for any other fact (a
  sanction, an obligation, a status). `end_fact(...)` to close one — pass
  its own `narration` describing the closing event too; a bare
  `end_fact()` means the agent learns a consequence started but never
  that it ended.

Default `visibility="public"` for anything a norm would plausibly want
tracked (this project's adopted norms consistently specify public
ledgers/monitors) — `"agent_only"` only for something strictly between
one agent and the mechanism. **Public narration is always third person**
(the agent's own name, never "you") — the same string is read by both the
affected agent and every bystander it's visible to. Check
`state/fluents_schema.md` before naming a new fluent; reuse an existing
name for an existing concept.

## Role directives are auto-rendered — and required

`prompts/role_directives/{role}.md` — one file per `role_name` in the
`state/institution.json` catalog, in-world phrasing only.
`engine.llm_agents.render_role_directives()` concatenates the directive
for every role a given agent currently holds (via `roles.roles.role_holder()`,
checked against the catalog, never guessed from a fluent name alone) into
the persona template's `{role_directives}` slot automatically — you never
wire this yourself. **A role registered with no matching file is a
pre-commit error** (the institution drift check) — write the file in the
same round you register the role, not after. The directive must make the
responsibility explicit ("I am responsible for maintaining the community
catch ledger"), not leave the agent reasoning about an unexplained
generic question.
