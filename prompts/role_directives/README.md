# role_directives/

One file per `role_name` that has ever been defined, e.g. `monitor.md`,
`registrar.md`. This is the only place role-specific instruction text
lives — never inline role instructions in mechanism/phase code or in a
rendered agent prompt directly.

Each file holds in-world phrasing only. Never mention "mechanism,"
"fluent," "penalty function," internal state key names, or other code
terms — see `prompts/phrasing_map.json` for the fourth-wall boundary
that keeps mechanics out of rendered text.
