# Recipe: lifecycle_change

The norm's own text implies a bounded duration for a rule, action's
configured behavior, or object instance ("for five rounds," "until the
stock recovers"). Read `lifecycle-contract.md` first — the automatic vs.
manual split there is the entire content of this recipe.

| | |
|---|---|
| **Required** | Add `lifecycle` (`active_from_round`/`duration_rounds`/`expires_at_round`) to the relevant `state/config.json["rules"][action_name]` entry, or the relevant `state/objects.json` instance. |
| **Required** | Still open `rule_active` yourself on activation, exactly as for an indefinite rule — a `lifecycle` does not exempt you from this. |
| **Forbidden** | Assuming `tick_rule_lifecycles()` closes `rule_active` for anything *other* than the natural expiry it was actually given. An outright repeal (removing the config entry, or ending it early) still needs a manual `end_fact()`. |
| **Verify** | The entry's `duration_rounds`/`expires_at_round` math is correct relative to the current round number. The orchestrator's generic smoke test still resolves the type. If reachable within this round's own test budget, confirm the rule is still active before its expiry round and inactive after (via `tick_rule_lifecycles()` directly, or by inspecting `state/fluents.json` after ticking). |
