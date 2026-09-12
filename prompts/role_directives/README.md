# role_directives/

One file per `role_name` registered in `state/institution.json`'s
`"roles"` catalog, e.g. `monitor.md`, `registrar.md`. This is the only
place role-specific instruction text lives — never inline role
instructions in mechanism/action code or in a rendered agent prompt
directly.

**Every one of these is rendered automatically, for every role an agent
currently holds** — `engine.llm_agents.render_role_directives()` checks
`roles.roles.role_holder()` against each name in the institution's own
role catalog and concatenates every matching file's text into the
persona template's `{role_directives}` slot; an agent holding two roles
(the base `fisher` plus a rotating `recorder`, say) gets both. Add a file
here the same round a role is registered — a registered role with no
matching file is flagged by
`engine.simulate.norm_implementation_institution_errors()`'s drift check
before the round can commit, and raises directly (`render_role_directives()`)
the moment anyone actually holds that role, since a role assigned with no
way for its holder to learn what it means defeats the point of having one.

Each file holds in-world phrasing only. Never mention "mechanism,"
"fluent," "penalty function," internal state key names, or other code
terms — see `prompts/phrasing_map.json` for the fourth-wall boundary
that keeps mechanics out of rendered text.
