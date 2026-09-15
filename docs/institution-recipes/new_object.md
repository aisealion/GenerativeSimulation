# Recipe: new_object (Level 2, or 3 with a `custom_handler`)

A persistent noun/resource — a ledger, pool, permit, deposit account,
reputation/violation record. Never a decision (that's `new_action.md`);
never hand-mutated fluent state. Read `object-contract.md` first.

**First**: check `state/institution.json`'s `object_types` catalog for an
existing type to reuse parametrically.

| | |
|---|---|
| **Required** | `state/object_types/{type}.json` — `type_name`, `description`, `ownership`, `fields` (with defaults), `operations`, `permissions`, `visibility`. |
| **Required** | `state/institution.json` `object_types` catalog entry: `{name: {"description", "owner": "state/object_types/{type}.json"}}`. |
| **Required** | `state/objects.json` instance declaration for each instance the design calls for: `{"id": ..., "type": ...}` — **never a field value**. |
| **Conditional** | `objects/handlers/{type}.py` (`run(ctx, object_id, operation, by_agent_id=None, **kwargs)`) only if the five generic operations (deposit/withdraw/set/append/read) genuinely can't express the needed behavior — most objects need none. |
| **Conditional** | `lifecycle` on the instance if the norm implies a bounded duration — see `lifecycle_change.md`. |
| **Forbidden** | Seeding a field value in `state/objects.json` or `state/runtime.json` — defaults apply automatically on first touch. |
| **Verify** | `state/institution.json`'s catalog and `state/objects.json`'s instance(s) agree with what's on disk. The orchestrator's generic smoke test resolves the `custom_handler` (if any) structurally. A `tests/norm_checks/` test exercising the actual operations/permissions/visibility the design claims (a deposit that should succeed, one that should be denied, a field visible to one role and not another). |
