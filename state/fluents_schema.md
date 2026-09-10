# Fluent name registry

Canonical list of every `fluent` name ever introduced into
`state/fluents.json`, one line each: name, then a short description of
the concept it represents. The norm-implementer checks this before naming
a new fluent — CodeGraph indexes code structure, not string
literals, so it won't reliably catch a near-duplicate name for a concept
that already exists under a different name. Reuse an existing name for an
existing concept; only add an entry here when a round introduces a
genuinely new one, as part of that same round's edit.

| fluent name | represents |
|---|---|
| `fisher` | The base role every agent holds from round 0 — eligibility to act as a fisher. Assigned via `assign_role()`, never carries `narration` (deliberately invisible to the notice renderer — see CLAUDE.md's "Fluent narration and visibility"). |
| `dead` | Permanent — an agent whose running food balance (`runtime["payoff"]`) went negative in `actions/harvest.py`. Written by the fixed survival mechanic (`engine/physics.py`'s `apply_consumption()`/`is_dead()`), not a norm-implementer mechanism; never terminated once set. Always `visibility="public"`, narration in third person (not "you") since the same string is read by both the affected agent and everyone else it's visible to. |
| `norm_active` | The queryable *history* of which `norm_types` entry was actually enforced and for how long — `holder="community"`, `args={"type": "<the norm_types key>"}` (a dict, not a list — the one deliberate exception to every other fluent's `args` shape, since a norm type has no single agent to key off). Opened via `set_fact()` the same round `state/config.json`'s `"norms"` list activates a type, closed via `end_fact()` the round it's removed/replaced — this is what actually answers "was this norm in force during round N," which `state/institution.json`'s `norm_types` catalog (static: what types *exist*) deliberately does not track. Never confuse the two: `norm_types` changes only when a genuinely new shape is invented; `norm_active` changes every time a round's config activates or deactivates one. |
| `seasonal_reserve_active` | Indicates a seasonal reserve accumulation period is in effect — tracks periods where fishers contribute a percentage of their catch to a shared communal reserve that must meet a season-end target. |
| `reserve_deposit` | Records a specific fisher's contribution to the shared seasonal reserve, typically a percentage (e.g., 10%) of their allowed catch. |
| `proportional_debt` | Indicates a fisher owes an additional deposit from a season-end reserve shortfall, calculated proportionally based on their seasonal catch relative to total community catch. |
| `penalty_trip_assigned` | Indicates a fisher has been assigned a penalty trip for violating catch limits (exceeding 5kg or violating 15% stock rule). Each penalty requires the fisher to take a mandatory 1kg trip. |
| `penalty_trip_served` | Indicates a fisher has served/completed a penalty trip, counting toward clearing their pending penalty obligations. |
