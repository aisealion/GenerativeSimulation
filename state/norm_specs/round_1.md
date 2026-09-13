# Round 1 Implementation Specification

This round introduces a communal pool object type that allows fishers to deposit surplus fish and withdraw as needed. The object type is defined in `state/object_types/communal_pool.json` and registered in `state/institution.json`.

## Object Type: communal_pool
- **Ownership**: COMMUNAL
- **Fields**: `balance_kg` (number, default 0.0)
- **Operations**: `deposit`, `withdraw`, `read`
- **Permissions**: All agents may write and read.
- **Visibility**: `balance_kg` visible to all.
- **Introduced Round**: 1

The runtime loads this specification via `load_object_types` and makes the object usable through `ObjectRuntime`.
