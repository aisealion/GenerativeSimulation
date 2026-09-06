# phases/

One instruction template per phase, filled from `state/runtime.json` +
`state/config.json` at render time. Add `{phase_name}.md` here alongside
the phase's `.py` file whenever a new phase is introduced — this is the
only prompt edit a new phase should ever require.

Rendered text must stay in-world; internal state key names and numeric
mechanics belong in `prompts/phrasing_map.json`, not here.
