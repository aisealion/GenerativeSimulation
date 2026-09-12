# Rule: the generic per-action extension point that replaces the old,
# harvest-only norms/*.py + NormEngine mechanism. A Rule attaches to
# exactly one action (state/config.json["rules"][action_name]) and can
# hook every stage of that action's execution — round-wide, whole-action,
# and per-agent — plus the two round-boundary hooks that run once
# regardless of which actions execute this round. This directly answers
# the actual structural problem the old design had: only harvest ever
# built a NormEngine, so only harvest could host a rule at all. Every
# action now has the identical mechanism available; whether a given round
# actually needs one is a real question, not a foregone one.
#
# Files live under actions/rules/{action_name}/ — one subpackage per
# action, auto-discovered by type_name the same way the old norms/
# directory was (engine.institution.registry.discover_subclasses), so
# adding a new rule is still "add a file," never a registry edit. Ships
# empty for every action, same "no seed content" principle norms/ always
# had — a pre-built shape would let a round tune parameters on an
# already-correct implementation instead of writing one from scratch.

import importlib
from dataclasses import dataclass

from engine.institution.lifecycle import is_active, tick
from engine.institution.registry import discover_subclasses


class Rule:
    """Base class for one entry under actions/rules/{action_name}/. Every
    hook is optional (all default to a no-op) — implement only the ones a
    given rule actually needs. `self.key`/`self.params` mirror the old
    Norm contract exactly (never persist anything on self between hooks;
    a fresh instance is built every round — use ctx.rule_state(self.key)
    for anything that must survive across rounds)."""

    type_name: str = None  # set by every subclass; unique within its own action's rule directory

    def __init__(self, key, params):
        self.key = key
        self.params = params

    # --- round-level: fires once per round, independent of any one action ---

    def before_round(self, state, round_number):
        """Once per round, before ANY action in this round's schedule has
        run. `state` is the full round-state dict (no single ActionContext
        exists yet at this point — nothing has been resolved to one
        action's participants)."""
        return None

    def after_round(self, state, round_number):
        """Once per round, after EVERY action in this round's schedule has
        already run."""
        return None

    # --- action-level: fires once per round for this rule's own action ---

    def before_action(self, ctx):
        """Once, before this action's own participants are processed this
        round. `ctx` is the action's ActionContext."""
        return None

    def after_action(self, ctx, round_record):
        """Once, after this action's round_record has been fully built —
        may mutate `round_record` and/or `ctx.state` directly (a stock
        override, a tally adjustment, a community-wide consequence). This
        is where a "the whole action's outcome" rule belongs, as opposed
        to a per-agent one."""
        return None

    # --- per-agent: only meaningful for an action whose handler calls
    # these explicitly inside its own per-agent loop (every handler in
    # this project does, including the generic Level-2 path) ---

    def is_eligible(self, ctx, agent_id):
        """False skips this agent's LLM call entirely this round (a live
        ban). Called at most once per agent per round."""
        return True

    def describe(self, ctx, agent_id):
        """One already-in-world-phrased sentence describing whatever this
        rule currently has to say to this agent, or None. Every active
        rule's non-None output is joined into one constraints line."""
        return None

    def after_agent(self, ctx, agent_id, record_entry):
        """Once per participating agent, right after their own
        record_entry dict has been built from their response — return a
        dict of fields to merge onto it (e.g. {"harvested_kg": 12.0,
        "note": "trimmed to the 15kg limit"}), or None for no change.
        Multiple rules run in state["config"]["rules"][action] order, each
        seeing the previous rule's already-applied patch on
        `record_entry` — this is the ordering-dependent chain (a reserve
        rule seeing a cap rule's already-trimmed number) the old
        raw_kg/proposed_kg threading provided; a rule needing the
        pre-any-rule original value re-derives it from a field no rule
        touches (harvest's own "effort" field, say), the same technique
        `engine.llm_agents._harvest_shortfall_clause()` already uses."""
        return None

    def on_agent_settled(self, ctx, agent_id, record_entry):
        """Once per agent, after EVERY rule's after_agent() has already
        applied its patch — `record_entry` here is the fully-settled
        final state, not the intermediate view after_agent() sees mid-chain.
        For a side effect that must react to the final outcome rather than
        any one rule's own contribution to it (starting a ban countdown
        because the settled record turned out to be a violation, say).
        Return value is ignored — this hook is for side effects
        (ctx.rule_state(self.key), ctx.objects, ctx.events), never for
        further patching record_entry itself; use after_agent() for that."""
        return None


@dataclass
class RuleSet:
    """Every active Rule for one action this round, in
    state["config"]["rules"][action_name] order — built fresh per
    ActionContext (see engine.institution.context.ActionContext), never
    cached, so a norm-implementer's mid-run edit to a rule file takes
    effect immediately."""

    rules: list

    @classmethod
    def for_action(cls, config, action_name, round_number=None):
        """`round_number=None` (the default) validates every entry —
        type resolves, key is unique — and includes all of them,
        active or not; passing a real `round_number` additionally filters
        out anything whose own `lifecycle` has expired or not started."""
        rule_types = discover_rule_types(action_name)
        specs = config.get("rules", {}).get(action_name, [])
        rules = []
        seen_keys = set()
        for i, spec in enumerate(specs):
            rule_type = spec.get("type")
            rule_cls = rule_types.get(rule_type)
            if rule_cls is None:
                raise ValueError(
                    f"state/config.json rules[{action_name!r}][{i}]: unknown rule type "
                    f"{rule_type!r} — must be one of {sorted(rule_types)}"
                )
            key = spec.get("id", rule_type)
            if key in seen_keys:
                raise ValueError(
                    f"state/config.json rules[{action_name!r}][{i}]: duplicate rule key {key!r} "
                    f'— set an explicit "id" to disambiguate multiple rules of the same type'
                )
            seen_keys.add(key)
            if round_number is not None and not is_active(spec.get("lifecycle"), round_number):
                continue
            rules.append(rule_cls(key=key, params=spec))
        return cls(rules)

    def is_eligible(self, ctx, agent_id):
        """AND across every active rule — one veto is enough to skip the
        LLM call. Every rule's is_eligible() still runs regardless (a ban
        countdown must always tick), only the combined boolean result
        short-circuits the call."""
        eligible = True
        for rule in self.rules:
            if not rule.is_eligible(ctx, agent_id):
                eligible = False
        return eligible

    def describe_constraints(self, ctx, agent_id):
        lines = (rule.describe(ctx, agent_id) for rule in self.rules)
        return " ".join(line for line in lines if line)

    def ineligibility_note(self, ctx, agent_id):
        return self.describe_constraints(ctx, agent_id) or (
            "Something about the community's current rules held you back this round."
        )

    def apply_after_agent(self, ctx, agent_id, record_entry):
        """Runs every rule's after_agent() in order, merging each
        returned patch onto record_entry in place — a "note" value
        concatenates onto any existing one (so two contributing rules
        both get heard) rather than overwriting it; every other field is
        a plain overwrite. Returns record_entry for convenience."""
        for rule in self.rules:
            patch = rule.after_agent(ctx, agent_id, record_entry)
            if not patch:
                continue
            for field_name, value in patch.items():
                if field_name == "note" and record_entry.get("note") and value:
                    record_entry["note"] = f"{record_entry['note']} {value}".strip()
                else:
                    record_entry[field_name] = value
        return record_entry

    def settle_agent(self, ctx, agent_id, record_entry):
        """Call once, right after apply_after_agent() — runs every rule's
        on_agent_settled() with the now-fully-patched record_entry.
        Kept as its own explicit call (not folded into apply_after_agent()
        itself) so a handler can inspect/log the settled record between
        the two if it wants to, and so it's obvious at the call site that
        every rule's own patch is already final by the time settlement
        hooks run."""
        for rule in self.rules:
            rule.on_agent_settled(ctx, agent_id, record_entry)

    def before_action(self, ctx):
        for rule in self.rules:
            rule.before_action(ctx)

    def after_action(self, ctx, round_record):
        for rule in self.rules:
            rule.after_action(ctx, round_record)


def discover_rule_types(action_name):
    """Every Rule subclass under actions/rules/{action_name}/, keyed by
    type_name — {} if that action has no rules directory at all yet (a
    brand-new action nobody has attached a rule to), never an error."""
    try:
        package = importlib.import_module(f"actions.rules.{action_name}")
    except ModuleNotFoundError:
        return {}
    return discover_subclasses(package, Rule, "type_name")


def all_configured_rules(config, round_number=None):
    """Every Rule instance across every action in
    state["config"]["rules"], flattened — what engine/simulate.py's
    run_cycle() calls before_round()/after_round() on, since those two
    hooks fire once per round regardless of which action a rule is
    otherwise attached to."""
    rules = []
    for action_name in config.get("rules", {}):
        rules.extend(RuleSet.for_action(config, action_name, round_number).rules)
    return rules


def tick_rule_lifecycles(config, fluents, round_number):
    """Call once per round, before the schedule runs — closes any rule's
    `rule_active` fluent (see state/fluents_schema.md) the exact round its
    own "lifecycle" (a state["config"]["rules"][action][i]["lifecycle"]
    entry) naturally expires, so a rule given a bounded duration never
    needs the norm-implementer to hand-write termination logic or
    remember to close rule_active itself. A no-op for any rule with no
    lifecycle set. `args` is keyed by both action and type — a type_name
    is only unique within its own action's rule directory, so both are
    needed to identify which rule_active record this is."""
    from roles.roles import end_fact

    for action_name, specs in config.get("rules", {}).items():
        for spec in specs:
            lifecycle = spec.get("lifecycle")
            if not lifecycle:
                continue
            event = tick(lifecycle, round_number)
            if event is None:
                continue
            rule_type = spec.get("type")
            end_fact(
                fluents, "rule_active", {"action": action_name, "type": rule_type}, round_number,
                narration=f"The rule covering {rule_type} (for {action_name}) has expired.",
                visibility="public", event_type="rule_deactivated",
            )
