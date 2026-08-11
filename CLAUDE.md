# GenerativeSimulation

## Prompt layer rules

The `prompts/` tree is the only place agent-facing text lives. It stays
fourth-wall clean: no internal state key names, code identifiers, or the
words "mechanism," "norm," "fluent," "penalty function" ever appear in
rendered prompt text.

- `prompts/persona_template.md` — static skeleton per agent. Slots are
  filled at render time from current state; never edited per-round or
  per-agent.
- `prompts/role_directives/` — one file per `role_name`, in-world
  phrasing only. The only place role-specific instruction text lives.
- `prompts/phases/` — one instruction template per phase, filled from
  `state/runtime.json` + `state/config.json` at render time.
- `prompts/phrasing_map.json` — maps internal state keys to in-world
  phrases. This is the fourth-wall boundary: internal names and numeric
  mechanics never appear in rendered text directly, only their mapped
  phrasing.

### Routing a rule change

- **role_fluent, role_name already has a file in `prompts/role_directives/`**:
  fully parametric — no prompt files touched.
- **role_fluent, role_name is new**: write the config/fluent schema as
  usual, AND add exactly one new file
  `prompts/role_directives/{role_name}.md` with in-world instruction
  phrasing. This is the only prompt edit a role change should ever
  require.
- **new_phase**: same rule — add `prompts/phases/{phase_name}.md`
  alongside the phase's `.py` file.
- **Any other rule**: never touch `prompts/`. If you're tempted to edit
  an individual agent's rendered prompt directly, or hand-write text like
  "this round you are the monitor, your task is X" inline in
  mechanism/phase code, stop — that instruction belongs in
  `prompts/role_directives/monitor.md`, filled generically.

### Validating a prompt-layer change

- Grep any new file under `prompts/` for internal state key names, code
  identifiers, or "mechanism," "norm," "fluent," "penalty function" — any
  hit is a fourth-wall violation and must be rephrased.
- Confirm no diff touches a rendered/output prompt directly — only
  `prompts/persona_template.md`, `prompts/role_directives/*.md`, or
  `prompts/phases/*.md` are legitimate prompt-layer diffs.
