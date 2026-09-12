# actions/prompts/

A new action's own prompt template lives directly in its
`state/actions/{action_name}.json` spec, under `"prompt": {"template":
"..."}` — filled from `state/runtime.json` + `state/config.json` at
render time via `engine.llm_agents.render_action()`. Add it there
whenever a new action is introduced, alongside the rest of that same
spec (and, if it needs one, `actions/handlers/{action_name}.py`) — no
separate file. Whether the action uses the zero-code
`generic_agent_decision` path or a custom `actions/handlers/{name}.py`
handler, its `prompt.fields`/`build_fields()`-equivalent output is
rendered through the same spec-owned template via `call_fisher_agent()`
— nothing else needs to name this path.

**This directory now holds only prompt content that isn't owned by any
one action's own spec** — checked in this order by `render_action()`:
1. the calling action's own `state/actions/{name}.json`'s `prompt.template`;
2. any spec's `prompt.templates` dict (a sub-step of a multi-call action
   that isn't itself a top-level action name — see
   `state/actions/critique.json`'s own `critique_response`/
   `critique_finalize` entries, one dialogue exchange each, both owned by
   critique's spec but neither one critique's own action_name); then
3. `{name}.md` here, for anything genuinely not owned by an action spec
   at all (`clarify.md`, used by the standalone `engine/clarify_norm.py`
   tool, which runs outside the round action pipeline entirely). Add a
   file here only for this third case — a real per-action prompt belongs
   in its spec, not here.

Cross-cutting prompt content that isn't specific to one action
(`persona_template.md`, `role_directives/`, `phrasing_map.json`,
`memory_phrasing.py`) stays in top-level `prompts/`, unchanged by any of
this.

Rendered text must stay in-world; internal state key names and numeric
mechanics belong in `prompts/phrasing_map.json`, not here or in a spec's
own `prompt.template` — the fourth-wall rule applies identically
regardless of which of the two files the text physically lives in.
