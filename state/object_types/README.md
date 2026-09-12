# state/object_types/

One `{type_name}.json` file per institutional-object *type* (a pool, a
ledger, a permit, a tool) — the declarative `ObjectSpec` schema
`engine/institution/objects.py::ObjectRuntime` reads. Instances of a type
are *declared* in `state/objects.json` (`id`/`type`/an optional
`lifecycle` — never a field value), mirroring `actions/rules/{action_name}/`'s
own type/instance split (an `actions/rules/{action_name}/{type}.py` file
defines a shape; `state/config.json["rules"][action_name]` lists which
instances of it are active). This directory is only ever the catalog of
what *kinds* of object exist.

The actual mutable field values (a pool's current balance, a ledger's
entries) live in neither of those files — they're simulation-owned, in
`state["runtime"]["objects"][object_id]["fields"]`, seeded from this
file's own `fields` defaults the first time anything touches the object.
Keeping a declaration and its accumulating runtime values apart is
deliberate: exactly the same reason `state/config.json["rules"][action_name]`
entries never hold a rule's own running balance (that's
`runtime["rules"][key]`, via `ctx.rule_state(key)`) — a
norm-implementer-writable file must never also be where the running
simulation's own numbers live.

**Ships empty by design**, same principle and same reason as
`actions/rules/` (see that directory's own README): most norms that
introduce a communal pool or a shared ledger are fully expressible by
declaring a new type here — no seed content is included on purpose, so
the first norm that ever needs one is genuinely operationalized from
scratch, not just a pre-built shape with the numbers tuned.

## Shape

```json
{
  "type_name": "communal_pool",
  "description": "A shared reserve fishers deposit surplus into.",
  "ownership": "COMMUNAL",
  "fields": {"balance_kg": {"type": "number", "default": 0.0}},
  "operations": ["deposit", "withdraw", "read"],
  "permissions": {
    "WRITE": {"who": "ROLE:treasurer"},
    "READ": {"who": "ALL"}
  },
  "visibility": {
    "balance_kg": {"who": "ALL"}
  },
  "custom_handler": null,
  "introduced_round": 9
}
```

`permissions` gates what an *operation* may do
(`ObjectRuntime.deposit()`/`.withdraw()`/`.set()`/`.append()`, checked
against `WRITE`/`APPEND` respectively — `who` is `"ALL"`, `"NONE"`, or
`"ROLE:<role_name>"`, resolved via `roles.roles.current_holder()`, never
cached). `visibility` gates what `ObjectRuntime.read()` returns to a given
viewer, per field — separate from permissions on purpose: an object can
be world-readable but role-write-gated, or the reverse.

`custom_handler`, when set, names a filename stem under
`objects/handlers/` (also ships empty — see that directory's own README)
implementing behavior beyond the five generic operations, dispatched via
`ObjectRuntime.custom(object_id, operation, ...)`. Reach for this only
when a generic deposit/withdraw/set/append/read genuinely can't express
what the norm needs — the same "declarative first, code only when truly
necessary" principle behind every other pluggable layer in this project.
