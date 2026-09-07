# actions/

One instruction template per action, filled from `state/runtime.json` +
`state/config.json` at render time. Add `{action_name}.md` here alongside
the action's `.py` file whenever a new action is introduced — this is the
only prompt edit a new action should ever require.

Rendered text must stay in-world; internal state key names and numeric
mechanics belong in `prompts/phrasing_map.json`, not here.
