# Fluent name registry

Canonical list of every `fluent` name ever introduced into
`state/fluents.json`, one line each: name, then a short description of
the concept it represents. The norm-implementer checks this before naming
a new fluent (Step 1) — CodeGraph indexes code structure, not string
literals, so it won't reliably catch a near-duplicate name for a concept
that already exists under a different name. Reuse an existing name for an
existing concept; only add an entry here when a round introduces a
genuinely new one, as part of that same round's edit.

| fluent name | represents |
|---|---|
| `fisher` | The base role every agent holds from round 0 — eligibility to act as a fisher. Assigned via `assign_role()`, never carries `narration` (deliberately invisible to the notice renderer — see CLAUDE.md's "Fluent narration and visibility"). |
| `dead` | Permanent — an agent whose running food balance (`runtime["payoff"]`) went negative in `phases/harvest.py`. Written by the fixed survival mechanic (`engine/physics.py`'s `apply_consumption()`/`is_dead()`), not a norm-implementer mechanism; never terminated once set. Always `visibility="public"`, narration in third person (not "you") since the same string is read by both the affected agent and everyone else it's visible to. |
