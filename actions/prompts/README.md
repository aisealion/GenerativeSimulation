# actions/prompts/

One instruction template per action, filled from `state/runtime.json` +
`state/config.json` at render time. Add `{action_name}.md` here alongside
the action's `.py` file (in `actions/`, one level up) whenever a new
action is introduced — this is the only prompt edit a new action should
ever require. If the action subclasses `engine.action_base.SimpleAgentAction`,
this is the template `call_agent()`/`build_fields()` implicitly render
through `call_fisher_agent()` — nothing else needs to name this path.

Colocated with the action code that renders it, on purpose — moved out
of top-level `prompts/actions/` so a new action's two required files
(`actions/{name}.py`, `actions/prompts/{name}.md`) live next to each
other. Cross-cutting prompt content that isn't specific to one action
(`persona_template.md`, `role_directives/`, `phrasing_map.json`,
`memory_phrasing.py`) stays in top-level `prompts/`.

Rendered text must stay in-world; internal state key names and numeric
mechanics belong in `prompts/phrasing_map.json`, not here.
