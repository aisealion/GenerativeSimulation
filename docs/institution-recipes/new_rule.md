# Recipe: new_rule (Level 3)

A deterministic constraint/consequence attaches to an existing action —
no new agent judgment. Read `rule-contract.md` in full before starting;
this recipe assumes it.

**First**: check `state/institution.json`'s `rule_types` catalog for an
existing type (on *any* action) close enough to reuse or generalize
parametrically — a real run wrote 10 separate files reimplementing the
same handful of shapes. Only proceed past this line if nothing fits.

| | |
|---|---|
| **Required** | `actions/rules/{action_name}/{name}.py` — a `Rule` subclass with a unique `type_name` (unique within that action's subdirectory), overriding only the hooks it needs. |
| **Required** | Add `{"type": "{name}", ...params}` to `state["config"]["rules"][action_name]` — **in the same round**. A file with no config entry runs never. |
| **Required** | Open the `rule_active` fluent for this activation (`set_fact`, `holder="community"`, `args={"action": action_name, "type": type_name}`). |
| **Conditional** | If `type_name` is genuinely new (not in `state/institution.json`'s `rule_types` catalog before): add `{name: {"description", "owner": "actions/rules/{action_name}/{name}.py"}}` there, once. |
| **Conditional** | `lifecycle` on the config entry if the norm implies a bounded duration — see `lifecycle_change.md`. |
| **Conditional** | If replacing the action's currently-active rule (the normal case for a new adopted norm): replace that action's list rather than append, unless the new norm's text genuinely leaves the old concern untouched. |
| **Conditional** | A short entry in `actions/rules/README.md` — only if this shape is genuinely reusable and worth documenting there for a future round, not for every rule. |
| **Required** | `tests/norm_checks/` test covering every new conditional branch, exercised through the real action handler (e.g. `actions.handlers.harvest.run(ctx)`) against a minimal fabricated state — not a unit test of the class in isolation. |
| **Forbidden** | Editing a protected action/handler. Touching `state/schedule.json`. Editing a *different* action's rule list unless the norm genuinely concerns that action too. A bare `self.params.get(key)` with no default — always supply one. |
| **Verify** | `python3 -m py_compile`. `pytest tests/norm_checks/ tests/regression/`. **Open `state/config.json` on disk and confirm the type actually appears there** — not your memory of having written it. Grep your new file for `.params.get(`/`self.params.get(` and confirm every match has a second argument. |

The activation step above is the single most common way a round is
written but never enforces anything — see `rule-contract.md`'s own
evidence (10 of 11 committed rounds on a real run).
