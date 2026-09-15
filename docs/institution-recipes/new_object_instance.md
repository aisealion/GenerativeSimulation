# Recipe: new_object_instance

A second (or later) instance of an **already-existing** object type — no
new type, no new fields/permissions.

| | |
|---|---|
| **Required** | `state/objects.json` entry: `{"id": "<new_unique_id>", "type": "<existing_type_name>"}`. |
| **Forbidden** | Seeding a field value here — defaults from the type's own spec apply automatically on first touch. Redefining the type's `fields`/`permissions`/`visibility` per-instance — those live only on the type. |
| **Verify** | The new `id` is unique among `state/objects.json` entries. Whatever action/rule is meant to use this instance actually references its `id` (not the type name, not another instance's `id`). |
