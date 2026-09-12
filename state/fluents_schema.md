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
| `dead` | Permanent — an agent whose running food balance (`runtime["payoff"]`) went negative in `actions/handlers/harvest.py`. Written by the fixed survival mechanic (`engine/physics.py`'s `apply_consumption()`/`is_dead()`), not a norm-implementer mechanism; never terminated once set. Always `visibility="public"`, narration in third person (not "you") since the same string is read by both the affected agent and everyone else it's visible to. |
| `rule_active` | The queryable *history* of which `rule_types` entry was actually enforced, for which action, and for how long — `holder="community"`, `args={"action": "<action_name>", "type": "<the rule_types key>"}` (a dict, not a list — the one deliberate exception to every other fluent's `args` shape, since a rule type has no single agent to key off, and needs both action+type to be unique since a type_name is only unique within its own action's rule directory). Opened via `set_fact()` the same round `state/config.json`'s `"rules"[action_name]` list activates a type, closed via `end_fact()` the round it's removed/replaced (or automatically, on natural lifecycle expiry — see `engine.institution.rules.tick_rule_lifecycles()`) — this is what actually answers "was this rule in force during round N for this action," which `state/institution.json`'s `rule_types` catalog (static: what types *exist*) deliberately does not track. Never confuse the two: `rule_types` changes only when a genuinely new shape is invented; `rule_active` changes every time a round's config activates, deactivates, or a rule's own duration expires one. |
