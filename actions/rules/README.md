# actions/rules/

One subdirectory per action (`harvest/`, `propose/`, `critique/`,
`vote/`, `discuss/`, and any new one a round adds under `actions/rules/{name}/`)
holding that action's own **rule** plugins — a per-agent constraint (a
cap, a reserve, a ban), a whole-action adjustment (a tally override, a
stock override), or a round-boundary hook. `actions/handlers/{name}.py`
implements *how the action itself works*; a rule implements *a constraint
or consequence around it*. A new adopted norm becomes either a config
change activating an *already-created* rule from an earlier round, or a
new small rule file — never a rewrite of any action's own handler, which
contains no rule-specific logic at all.

**Every action's own subdirectory ships empty of rules by design** — no
seed/example `Rule` implementations, on purpose (the same reasoning that
kept top-level `norms/` empty before this directory replaced it — see
CLAUDE.md). Round 1 must always operationalize its adopted norm from
scratch: a pre-built cap/reserve/ban rule sitting here from the start
would let the norm-implementer just tune parameters on an
already-correct implementation instead of actually writing one, which
defeats the point of studying whether it can.

## Why per-action, not one flat directory

Every action gets the *identical* rule-hosting mechanism — harvest never
had a special capability the others lacked; it just happened to be the
only one anyone had wired one into. Organizing rules by which action they
modify makes that visible directly in the file tree, and it's what makes
`engine.institution.rules.discover_rule_types(action_name)` need no
registry at all: it just imports `actions.rules.{action_name}` and scans
it, the same auto-discovery-by-subclass pattern this project always uses
for a pluggable kind.

## How it's wired together

Every action, when it runs (`engine.institution.runtime.ActionRuntime.run_action()`),
builds a `RuleSet` (`engine.institution.rules.RuleSet.for_action()`) from
`state["config"]["rules"][action_name]` — the list of `{"type", "id"?,
...params}` entries currently active for *that* action. Three tiers a
rule can hook, all real for every action, not just harvest:

- **Whole-action**, called automatically by `ActionRuntime` itself:
  `before_action(ctx)` before the handler runs, `after_action(ctx,
  round_record)` after it returns — this is where a stock override or a
  tally adjustment belongs.
- **Per-agent**, called by whichever handler owns this action's own loop
  (every handler in this project calls these, including the generic
  zero-code Level-2 path, so a Level-2 action gets this for free):
  `is_eligible(ctx, agent_id)` (return `False` to skip that agent's LLM
  call entirely — a live ban), `describe(ctx, agent_id)` (one sentence for
  the constraints line), `after_agent(ctx, agent_id, record_entry)`
  (return a dict of fields to patch onto that agent's own record — a
  trimmed harvested_kg, an added note — chained across rules, see below),
  `on_agent_settled(ctx, agent_id, record_entry)` (called once every rule
  in the chain has already applied its own `after_agent()` patch — use
  this for a side effect that needs to see the *final* settled outcome,
  such as depositing whatever was actually trimmed off, not just what
  this one rule alone would have trimmed).
- **Round-boundary**, independent of any single action — see below.

Rules for one action run **in `state["config"]["rules"][action_name]`
order** — each sees the previous one's already-applied `after_agent()`
patch, so a reserve-shaped rule genuinely can run after a cap-shaped one
and see the cap's own trimmed number (recovering the pre-any-rule
original from a field no rule touches — harvest's own `effort`, say — the
same technique `engine.llm_agents._harvest_shortfall_clause()` already
uses).

Two hooks fire once per **round**, independent of any single action:
`before_round(state, round_number)` / `after_round(state, round_number)`
— every rule across every action's own list gets these called, once,
before/after the whole round's schedule runs (`engine/simulate.py`'s
`run_cycle()`). Use these for something that isn't really about one
action at all (a community-wide check that should happen once a round,
regardless of which actions ran).

See `engine/institution/rules.py`'s `Rule` class for the full hook
contract and default no-op behavior — that file is off-limits to edit,
but its docstrings are the actual spec for what each hook does and when
it's called.

## Worked example (hypothetical — illustrates the pattern, not a real rule)

A norm like "each fisher may keep up to 12kg per trip; anything beyond
that goes into a shared reserve; a fisher who brings in less than 5kg may
draw up to 4kg from the reserve to top up; two violations of the cap in a
row means a two-trip ban" would, if these three rule *shapes* already
existed from an earlier round, become pure configuration for
`state["config"]["rules"]["harvest"]` — no new rule file needed for a
round that just wants different numbers on an already-existing shape:

```json
{
  "rules": {
    "harvest": [
      {"type": "example_cap", "limit_kg": 12},
      {"type": "example_reserve", "shortfall_threshold_kg": 5, "max_withdrawal_kg": 4},
      {"type": "example_ban", "trigger_sanction": "over_cap", "trips": 2}
    ]
  }
}
```

Note the order: a reserve-shaped rule must come *after* a cap-shaped one
specifically because it deposits whatever the previous rule in the chain
already trimmed off — reversing the order would mean it runs before
there's anything to deposit, and the reserve would never grow. This
ordering rule is general — it applies to any two rules in a
deposit/withdraw relationship, for any action, not specifically to rules
named `example_cap`/`example_reserve` (which don't exist; name your own
descriptively for what they actually do).

Since nothing exists here by default (see above), the very first rule any
round adopts is always genuinely new: add a
`actions/rules/{action_name}/{name}.py` file subclassing `Rule` with a
unique `type_name`; it's picked up automatically by
`engine.institution.rules.discover_rule_types()`, no registry edit
required. A *later* round whose norm matches an *already-created* rule's
shape, just with different numbers, can then configure it directly
instead of writing another one.

## How a norm gets verified before it's committed

The norm-implementer writes a formal requirement list to
`state/norm_specs/round_{N}.md` *before* touching any code (its own
institutional design step), classifying each requirement's clarity and
resolving anything ambiguous or incomplete via a short dialogue with the
fisher who proposed the rule. Once code exists, a separate
`norm-evaluator` subagent — with no access to `actions/rules/`/`prompts/`,
only to its own `tests/norm_evaluation/` — writes and runs independent
tests against that spec and classifies each requirement as compliant, an
implementation error, or a remaining spec gap. See
`.opencode/agent/norm-evaluator.md` for the full contract, and CLAUDE.md
for why this is a second agent rather than another self-check inside the
norm-implementer.
