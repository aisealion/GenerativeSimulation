# Lifecycle contract — bounded duration

`lifecycle` is an optional dict attached to a `state/config.json["rules"][action]`
entry or a `state/objects.json` instance: `active_from_round`/
`duration_rounds`/`expires_at_round`. Omit it entirely for anything meant
to run indefinitely (the default) — only set it when the norm's own text
implies a bounded duration ("for the next five rounds," "until the stock
recovers to X").

## What's automatic

`tick_rule_lifecycles()` runs every round, before the schedule, and
auto-closes a rule's `rule_active` fluent the exact round its duration
naturally lapses — no bookkeeping required for that specific case.

## What's still manual, always

- **Opening** `rule_active` when a rule first activates — every time,
  lifecycle or not. See `rule-contract.md`'s activation section.
- **Closing** `rule_active` for an **outright repeal** — replacing or
  removing a config entry that had no lifecycle, or ending one early
  before its natural expiry. `tick_rule_lifecycles()` only ever handles
  natural, already-declared expiry.

Getting this half-automatic split backwards (assuming lifecycle closes
everything, or assuming you never need to open it because "it'll expire
anyway") is the same class of silent-no-op gap as forgetting to activate
a rule in the first place — the fluent record is what answers "was this
rule in force during round N" later; a rule that ran but never opened its
own `rule_active` record looks, to that history, like it never ran at
all.
