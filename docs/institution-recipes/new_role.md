# Recipe: new_role

A new institutional responsibility — a role someone holds, distinct from
any decision that role later makes (that's `new_action.md`) or process
that responds to the decision (its own separate requirement). Read
`role-contract.md` first.

| | |
|---|---|
| **Required** | `state/institution.json` `roles` entry: `{"exclusive": bool, "description": ..., "introduced_round": N}`. |
| **Required** | `prompts/role_directives/{role}.md` — in-world phrasing making the responsibility explicit, in the **same round** the role is registered. A role with no matching file is a pre-commit error. |
| **Conditional** | `assign_role(role_name, agent_id, fluents, round_number, exclusive=True)` if the norm calls for someone to actually hold the role starting this round (as opposed to only defining that the role exists for a later action to require). **Always pass `exclusive=True` for a rotating/single-holder role** — the default silently breaks rotation (see `role-contract.md`). |
| **Conditional** | If an action structurally requires this role: set that action's `roles.actor_role` to the role name (only for a *new* action you're also adding this round — never edit an existing action's `actor_role`). |
| **Forbidden** | Caching "who currently holds this role" anywhere in `state/institution.json` (an `active_roles` map, an ad hoc field). That answer lives only in `state/fluents.json`, read via `current_holder()`. |
| **Verify** | Institution drift check: role registered ⟺ directive file exists. If the norm calls for an actual holder now: `state/fluents.json` has a matching role-fluent record (grep your diff for `assign_role(`/`set_fact(`). If exclusive: confirm only one holder record is ever open at a time after a rotation (test it, don't assume). |
