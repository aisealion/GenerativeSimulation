# Recipe: participation_change

Who participates in an action changes — e.g. from "every alive fisher"
to "only whoever holds a specific role."

| | |
|---|---|
| **Required** | Edit `participation` on the relevant action's own `state/actions/{name}.json` — `{"policy": "all_alive_fishers"}` or `{"policy": "role_holders", "role": "<name>"}`. Only legal on a **new** action you're adding this round, or (per `architecture.md`) a protected/earlier action is off-limits regardless of what's being changed. |
| **Conditional** | If switching to `role_holders`, that role must already exist or be added this same round — see `new_role.md`. |
| **Forbidden** | Editing a protected existing action's `participation` — if an existing action's participants must change, that's "stop and report, needs a human." |
| **Verify** | `ActionContext.build(...)`'s resolved `.participants` matches the new policy for a fabricated state with a mix of eligible/ineligible agents (dead, wrong role, etc.). |
