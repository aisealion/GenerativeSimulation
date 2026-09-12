# actions/prompts/

One instruction template per action, filled from `state/runtime.json` +
`state/config.json` at render time. Add `{action_name}.md` here whenever
a new action is introduced (alongside `state/actions/{action_name}.json`
and, if it needs one, `actions/handlers/{action_name}.py`) — this is the
only prompt edit a new action should ever require. Whether the action
uses the zero-code `generic_agent_decision` path or a custom
`actions/handlers/{name}.py` handler, its `prompt.fields`/`build_fields()`-
equivalent output is rendered through this same template via
`call_fisher_agent()` — nothing else needs to name this path.

Colocated with `actions/handlers/`, not with `state/actions/` (the spec
files) — a new action's required prompt lives next to the code that
might render it, even for a Level-2 action with no code file of its own.
Cross-cutting prompt content that isn't specific to one action
(`persona_template.md`, `role_directives/`, `phrasing_map.json`,
`memory_phrasing.py`) stays in top-level `prompts/`.

Rendered text must stay in-world; internal state key names and numeric
mechanics belong in `prompts/phrasing_map.json`, not here.
