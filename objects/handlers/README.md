# objects/handlers/

Custom logic for an institutional-object *type* that the five generic
operations (`deposit`/`withdraw`/`set`/`append`/`read`, see
`engine/institution/objects.py::ObjectRuntime`) can't express — the
Level-3 escape hatch for objects, mirroring `actions/rules/{action_name}/`'s
own role for per-action constraints.

**Ships empty by design**, same principle as `actions/rules/` (see that
directory's own README): most institutional objects a norm actually
introduces (a pool, a ledger, a permit) are fully expressible through the
generic operations plus a declarative `state/object_types/{type}.json`
spec — reaching for a custom handler when a generic operation would do
defeats the point of keeping the norm-implementer's object-code surface
small, the same way a pre-built rule would defeat the point of studying
whether a norm can be operationalized from scratch.

## Contract

One file per handler, named for the `custom_handler` value that
references it (`state/object_types/{type}.json`'s own field — a filename
stem, not a class name). Each file exposes exactly one function:

```python
def run(runtime, object_id, operation, by_agent_id=None, **kwargs):
    """`runtime` is the calling ObjectRuntime — use its own
    deposit/withdraw/set/append/read for simple field mutations, its
    `.fluents`/`.round_number` for a `roles.roles.current_holder()`
    permission lookup, and `.events.emit(...)` for an announcement beyond
    what those generic operations' own `narration` kwarg already covers.
    `object_id` names the instance (its declaration lives in
    state/objects.json; its mutable field values in
    state["runtime"]["objects"][object_id]["fields"]) — never read or
    write either file directly. Unlike the five generic operations, this
    function is responsible for its own permission checking; nothing
    upstream of it enforces one."""
    ...
```

Invoked via `ObjectRuntime.custom(object_id, operation, by_agent_id=..., **kwargs)` —
never called directly by anything else.
