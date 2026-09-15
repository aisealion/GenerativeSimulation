# Rule contract — `actions/rules/{action_name}/{name}.py`

A rule attaches to **exactly one action — every action, not only
harvest.** Pick the action a requirement is actually *about*; harvest
having more historical rules attached to it is not a reason to attach a
new one there too.

A file defines exactly one `Rule` subclass (`from engine.institution.rules
import Rule`) with a unique `type_name` (unique **within its own action's
subdirectory** — a different action can reuse the same `type_name` for
something unrelated), overriding any of:

## Per-agent hooks

Only meaningful for an action that calls the fisher agent once per
participant (every action in this project does):

- `is_eligible(self, ctx, agent_id) -> bool` — `False` skips this agent's
  turn entirely this round (a live ban). Called once per agent per round.
- `describe(self, ctx, agent_id) -> str | None` — one already-in-world
  sentence for this agent right now, or `None`. Joined with every other
  active rule's output into that action's own constraints line.
- `after_agent(self, ctx, agent_id, record_entry) -> dict | None` — once
  per participating agent, right after their response becomes
  `record_entry`. Return a dict of fields to patch onto it, or `None`.
  Rules for the same action run **in `state["config"]["rules"][action_name]`
  order** — each sees the previous rule's already-applied patch (a
  reserve rule seeing a cap rule's already-trimmed number). A `"note"`
  patch **concatenates** onto any existing one; every other field is a
  plain overwrite. Need the pre-any-rule original value? Re-derive it
  from a field no rule touches (harvest's own `"effort"`) — the same
  technique `engine.llm_agents._harvest_shortfall_clause()` already uses,
  which is also what turns a `"note"` patch into something the affected
  agent actually reads next round, automatically.
- `on_agent_settled(self, ctx, agent_id, record_entry)` — once per agent,
  after **every** rule's `after_agent()` has applied its patch —
  `record_entry` here is the fully-settled final state. For a side effect
  reacting to the settled outcome (starting a ban countdown because the
  final record turned out to be a violation).

## Whole-action hooks

Called automatically by `ActionRuntime`, once per round, regardless of
whether the action has a per-agent loop at all:

- `before_action(self, ctx)` — before participants are processed.
- `after_action(self, ctx, round_record)` — after `round_record` is fully
  built. May mutate `round_record`/`ctx.state` directly — this is where a
  stock override or tally adjustment belongs (writes
  `ctx.state["runtime"]["stock_kg"]` and `round_record[...]` directly;
  there's no separate override method).

## Round-boundary hooks

Fire once per round for **every** configured rule across **every**
action, independent of which action a rule is filed under:

- `before_round(self, state, round_number)` — before any action in this
  round's schedule has run.
- `after_round(self, state, round_number)` — after every action has run.

## State

`ctx.rule_state(self.key)` — cross-round-persistent dict, backed by
`runtime["rules"][key]`. `ctx.round_scratch(self.key)` — this-round-only,
never persisted. `ctx.objects` — see `object-contract.md`. A rule
instance is rebuilt fresh every round — never rely on `self.<anything>`
surviving between rounds.

## The one rule that causes the most silent no-ops

**`self.params.get(key)` must always carry a default** —
`self.params.get(key, <sensible_default>)`, never a bare `.get(key)`. The
orchestrator smoke-tests *every registered rule type, for every action's
own directory*, not just what this round's config activates, by
instantiating each with `params={}` and calling every hook. A bare
`.get(key)` returns `None` there, and `None` reaching arithmetic crashes
the rule and discards an otherwise-correct round — a real round was
discarded exactly this way (`TypeError` from a string configured where a
number was expected, reaching an undefaulted `.get()`). Your own
config-value test can't catch this (it never has a reason to misconfigure
itself) — fix it in the code, always. Same rule for a custom
`actions/handlers/*.py`/`objects/handlers/*.py`'s own params.

## Activation — the single most common way a round does nothing

**A rule file has zero effect until its `type_name` is added to
`state["config"]["rules"][action_name]`, in the same round.**
Auto-discovery (`engine.institution.rules.discover_rule_types()`) makes
the class importable and registered, but
`RuleSet.for_action()` only instantiates types the config actually names.
A rule can compile, pass every smoke test, even get evaluated `COMPLIANT`,
while never once executing — a real 23-round run hit this in **10 of 11**
committed rounds (back when every rule lived in one flat list; the same
failure is exactly as possible per-action now). Writing the file is never
the last step — activating it is. A round replacing the currently-active
rule for an action should generally *replace* that action's list, not
append — keep an older entry only if the new norm genuinely leaves that
concern untouched.

## Fluent bookkeeping tied to activation

**Activating or deactivating a type also means opening or closing its
`rule_active` fluent** (`roles.roles.set_fact()`/`end_fact()`,
`holder="community"`, `args={"action": "<action_name>", "type": "<type>"}`
— see `state/fluents_schema.md`). This is what answers "was this rule in
force during round N" later — `state/config.json` only ever shows
*current* state. If the rule has a `lifecycle` with `duration_rounds`/
`expires_at_round`, **closing `rule_active` on natural expiry is
automatic** (`tick_rule_lifecycles()`, run every round before the
schedule) — you still open it yourself on activation, and you still close
it yourself for an outright repeal (no lifecycle, or ending one early). A
genuinely new type also needs a `state/institution.json` `rule_types`
entry, once, when invented — separate from `rule_active`, which changes
every round a type turns on/off/expires.
