# Recipe: state_extension

A genuinely new persistent value the institution needs to track, that
doesn't fit an existing rule param, object field, or fluent — e.g. a new
counter, a new top-level runtime field a rule reads across rounds.

Read `state-files.md` first and place the actual value in whichever file
already owns that *kind* of data (a rule's own `ctx.rule_state(self.key)`
for rule-scoped persistent state; an object field for anything
inventory-shaped; a fluent for anything interval-shaped; an event for
anything point-in-time). This recipe is for documenting that the field
now exists, not for inventing a new storage location — this project has
no general-purpose "extra state" file, and shouldn't get one.

| | |
|---|---|
| **Required** | Add a one-line description of the new field under `state/institution.json`'s `"state"` section. |
| **Forbidden** | Inventing a new top-level state file. Storing the value directly in `state/institution.json` itself if it changes more than once per round's institutional-shape edit — that file only changes on shape changes, not every round. |
| **Verify** | Institution drift check passes. The field is actually read/written from the location its own kind of data belongs in (per `state-files.md`), not duplicated across two files. |
