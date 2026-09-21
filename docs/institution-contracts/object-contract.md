# Institutional object contract — `state/object_types/`, `state/objects.json`

A norm may introduce an institutional object — a community ledger, a
communal reserve, a deposit account, a permit, a reputation/violation/
monitoring record. Declare it as a real institutional object — **never**
merely mention it in a prompt, and never as hand-mutated
`state/fluents.json` state (fluents are for facts/roles with a duration,
not something with its own numeric or list-shaped fields).

## Object type (`state/object_types/{type}.json`)

Check `state/institution.json`'s `object_types` catalog first — reuse an
existing type parametrically before writing a new one. Ships empty by
design (no seed types), same principle as `actions/rules/`.

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
  "visibility": {"balance_kg": {"who": "ALL"}},
  "custom_handler": null,
  "introduced_round": 9
}
```

`permissions` keys: `DISCOVER`/`READ`/`USE`/`WRITE`/`APPEND`/`TRANSFER`/
`ADMINISTER`/`DESTROY` (only `WRITE`/`APPEND`/`READ` are checked by the
five generic operations today — the rest are reserved for a
`custom_handler` to consult itself). Each rule is `{"who": "ALL"}`,
`{"who": "NONE"}`, or `{"who": "ROLE:<role_name>"}`. `visibility` gates
what a viewer may *see*, per field, separately from what an operation may
*do* — an object can be world-readable but role-write-gated, or the
reverse. Both resolve a `ROLE:` rule via `roles.roles.current_holder()`,
fresh every time — never cache a holder on the object.

## Object instance (`state/objects.json`)

A **declaration only** — `id`, `type`, optional `lifecycle`. **Never a
field value.**

```json
{"id": "communal_reserve", "type": "communal_pool"}
```

Mutable field values are simulation-owned, in
`state["runtime"]["objects"][object_id]["fields"]` — never seed or edit
them, for the same reason `state/runtime.json` is read-only: a
norm-engineer-writable file must never also be where the running
simulation's own accumulated numbers live, or a discard/revert would
either lose real data or leave a stale declaration pointing at numbers
that no longer make sense. A field's default (from the type's own spec)
applies automatically the first time anything touches the object.

## Using an object from code

A `Rule` hook or an `actions/handlers/{name}.py` handler reads/writes
through `ctx.objects` (an `ObjectRuntime`) — never by touching
`state/objects.json` or its runtime companion directly:

```python
ctx.objects.deposit(
    "communal_reserve", "balance_kg", overflow_kg, by_agent_id=agent_id,
    narration=f"{name} deposited {overflow_kg:.1f}kg into the reserve.",
)
```

`deposit`/`withdraw`/`set`/`append` all take an optional `narration` —
when given, it becomes exactly one round's worth of visible notice and
memory entry (an `Event` in `state/events.json` underneath — you don't
construct one directly), then disappears; an object's own *current*
values are always read live through `read()` (or a Level-2 action's
`prompt.fields`, `{"from": "object", ...}`), never cached as a fact.
Omit `narration` for a silent bookkeeping mutation nothing needs
announced. `read(object_id, field, viewer_agent_id=...)` returns `None`
(never raises) when that field isn't visible to that viewer.

## `custom_handler`

Only reach for this (a filename stem under `objects/handlers/`, a
`run(ctx, object_id, operation, by_agent_id=None, **kwargs)` function,
dispatched via `ctx.objects.custom(object_id, operation, ...)`) when a
genuinely new object type needs behavior the five generic operations
can't express — most objects a norm introduces need none. A custom
handler is responsible for its own permission checking; nothing upstream
enforces one.
