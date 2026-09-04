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
| `audit_violation` | Records that an agent failed to return excess catch as required. Initiated during weekly audit when ledger shows raw catch exceeded cap without proper return. Terminated after sanction is applied. Public visibility to inform community of rule enforcement. |
| `fishing_ban` | Indicates an agent is temporarily banned from fishing for one round due to an audit violation. Initiated at audit end for sanctioned agents, automatically terminates after one round. Used by `is_eligible()` to skip banned agents. |
| `communal_obligation` | Per-agent outstanding obligation (in kg) created when violating the 12kg cap. Must be satisfied within 2 trips through catch deductions or communal fee payment. Private visibility. |
| `obligation_deadline` | Per-agent counter tracking trips remaining to satisfy communal obligation. Starts at 2, decrements each trip. When reaching 0, remaining obligation is forcibly paid. Private visibility. |
| `communal_pool_kg` | Cumulative total of communal fees paid to the pool from obligation payments. Public visibility to inform agents of community resources. |
| `weekly_review` | Records that a community council review occurred in a specific round. Initiated at end of every 7th round to assess shared ledger and violations. Public visibility. |
