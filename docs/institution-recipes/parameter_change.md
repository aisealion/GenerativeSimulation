# Recipe: parameter_change (Level 1)

An existing, already-active rule type's value changes, or a bounded
duration is added — no new file, no new type.

| | |
|---|---|
| **Required** | Edit the value(s) in the matching `state/config.json["rules"][action_name]` entry. |
| **Conditional** | Add/edit `lifecycle` on that same entry if the norm implies a bounded duration — see `lifecycle_change.md`. |
| **Forbidden** | Touching the rule's own `.py` file for a value change alone. Touching a different action's rule list. |
| **Verify** | The orchestrator's generic runtime smoke test (every registered type, every action) resolves cleanly. If the value actually gates behavior differently, a `tests/norm_checks/` assertion on the new value is still worth adding — a config edit with no test is easy to typo silently. |

Read `rule-contract.md`'s activation section first if you're not certain
the type is *already* active — if it isn't, this is `new_rule.md` or
`new_object_instance.md` instead, not a bare parameter change.
