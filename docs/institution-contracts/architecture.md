# Institutional architecture — conceptual model

Read this once per round, before classifying requirements. The other
contract files in this directory go deeper on one piece each; this one is
the map of how the pieces fit together.

## The atomic unit: an action

An **action** is the atomic unit of agent decision-making — one
`call_fisher_agent()` call per action, per round (`harvest`, `propose`,
`critique`, `vote`, `discuss` today). "Decision" is broad: reporting,
inspecting, voting on a sanction, choosing to close something all count,
exactly as much as an effort/cap choice does.

Every requirement in an accepted norm routes to exactly one of four
levels, ordered by cost. Route by what the requirement actually **is**,
never by which level is cheapest to build:

| Level | Shape | Cost |
|---|---|---|
| **1** | A config value on an already-active rule type, or a `lifecycle` added to an existing rule/action/object entry. | No new file. |
| **2** | A new declarative institutional object, or a new action built entirely from the generic handler (`execution.handler: "generic_agent_decision"` — ask one question, record the answer). | One spec/type file, zero Python. |
| **3** | A new `actions/rules/{action}/{name}.py` type, or a small custom `actions/handlers/{name}.py` / `objects/handlers/{type}.py`. | Real logic, bounded by a fixed hook contract. |
| **4** | A genuinely new institutional decision no existing action/handler shape hosts. | Full new-action recipe, its own handler. |

A Level-4 action is one `run(ctx)` function, not a class hierarchy — read
`action-contract.md` before pricing anything as "too much new
infrastructure."

## Deterministic constraint vs. genuine agent judgment

A **rule** (`actions/rules/{action}/*.py`) is arithmetic over values that
already exist — a cap, a fee, a reserve deposit, a ban countdown. It has
no judgment. A verb where an actor weighs, judges, inspects, decides,
reviews-and-rules, verifies, contests, appeals, testifies, or exercises
discretion using information not already reduced to a number/boolean is
**action-shaped**, not rule-shaped, regardless of how much simpler a rule
file would be to write. Two failure directions are equally real: routing
a genuine judgment call into a rule file means the "decision" is never
actually made by anyone (a real round did this with a rotating "verifier"
who was supposed to weigh evidence and impose bans — nobody was ever
banned, because the decision was silently reduced to a comparison);
routing genuine arithmetic into a new action wastes a Level-4 budget for
no reason. Cost is never itself a legitimate reason to pick one over the
other.

A second, easy-to-miss action-shaped trigger: an actor **producing** a
value through their own perception/sampling/judgment (estimates, samples,
surveys, reports, observes) — action-shaped even when the simulation
already knows the "true" number internally. Silently substituting the
known value and labeling it "their estimate" deletes the institution the
norm described, it doesn't approximate it (a real round did exactly this
with a "watcher" whose stock estimate was just the real physics value
relabeled — no fisher was ever actually asked, for three rounds).

## Inventory vs. decision vs. rule

A third, orthogonal question: is this a decision at all, or is it
**inventory**? A communal pool, a ledger, a permit's remaining allowance
is state something else (a rule, an action) reads and writes — never a
decision anyone makes, never a new action just because the norm's text
introduces a new noun. See `object-contract.md`.

## Roles: structure vs. current holder

`state/institution.json`'s `roles` catalog and an action's own
`actor_role` describe **structure** — does this role exist, does it
rotate, does this action require it. They never say who holds it right
now. That's a live lookup, `roles.roles.current_holder(fluents,
role_name, round_number)`, answered fresh every time from
`state/fluents.json` — never cached in `state/institution.json`, because
that file only changes when the institution's *shape* changes, not every
round a rotation fires. See `role-contract.md`.

## Current-state files vs. history

`state/config.json` (rules) and `state/objects.json` (object instances)
show **current** state only. History lives elsewhere and is written
automatically, not by you: `state/institution_history.jsonl` (structural
changes, orchestrator-appended), and a `rule_active` fluent (when a rule
type was active, for which action, for how long — you open/close this
one yourself, see `rule-contract.md`).

## Interval facts vs. point-in-time occurrences

`state/fluents.json` holds **interval** facts — a genuine start and
possibly an end (roles, bans, `rule_active`). `state/events.json` holds
**point-in-time** occurrences — an object mutation, a one-off
announcement, nothing with a duration. Both are populated by simulation
code at run time (`ctx.events.emit(...)`, `ObjectRuntime`'s own
`narration` kwarg, `roles.roles.set_fact()`/`end_fact()`) — you almost
never hand-edit either file's content directly, only their *schema*
(`state/fluents_schema.md` for new fluent names).

## Compiled artifacts — never hand-edited

`state/schedule.json` is compiled every round from `state/institution.json`'s
action catalog plus each `state/actions/{name}.json`'s own
`scheduling.after`/`before`/`gate`. Need a new action to run between two
existing ones? That's an `after`/`before` value in the new action's own
spec — never a `state/schedule.json` edit (denied outright by
permission, and solving the wrong problem if you're tempted).

## Protected paths — additive only, permanently

`state/actions/{harvest,propose,critique,vote,discuss}.json` and their
`actions/handlers/*.py` pairs are permanently off-limits — and so is
every action any earlier round has ever added. "Additive only" doesn't
loosen after the first new action exists; a second round needing
something close to an earlier new action still gets its own new action,
never an edit to the first one. Enforced by a hard, dynamic orchestrator
check (`_actions_protected_as_of_head()` in `engine/simulate.py`, which
reads `state/institution.json` as of HEAD and protects everything it
lists, not just the original five) — independent of whatever the
permission YAML does or doesn't block.

## Reuse before creating

Before writing any new rule type, action, or object type, check
`state/institution.json`'s `rule_types`/`object_types` catalogs (fast,
already-summarized, and each entry's `owner` path tells you which action
it belongs to) — a real run accumulated 10 separate rule files
reimplementing the same handful of cap/reserve shapes from scratch,
never once reusing an earlier one.
