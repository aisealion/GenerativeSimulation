from engine.institution.context import ActionContext
from engine.institution.rules import Rule, RuleSet


class _AlwaysEligible(Rule):
    type_name = "_always_eligible"


class _NeverEligible(Rule):
    type_name = "_never_eligible"

    def is_eligible(self, ctx, agent_id):
        return False


class _CountsCalls(Rule):
    """Confirms every rule's is_eligible() runs even after an earlier rule
    already vetoed — side effects (a ban countdown tick) must not be
    short-circuited."""
    type_name = "_counts_calls"
    call_count = 0

    def is_eligible(self, ctx, agent_id):
        _CountsCalls.call_count += 1
        return True


def _ctx(rules):
    state = {
        "config": {"rules": {"_test_action": []}}, "fluents": [], "runtime": {"stock_kg": 100.0},
        "agents": {}, "round_number": 1,
    }
    ctx = ActionContext.build({"name": "_test_action"}, state, 1)
    ctx.rules = RuleSet(rules)
    return ctx


def test_is_eligible_true_when_all_rules_agree():
    ctx = _ctx([_AlwaysEligible(key="a", params={})])
    assert ctx.rules.is_eligible(ctx, "agent_0") is True


def test_is_eligible_false_if_any_rule_vetoes():
    ctx = _ctx([_AlwaysEligible(key="a", params={}), _NeverEligible(key="b", params={})])
    assert ctx.rules.is_eligible(ctx, "agent_0") is False


def test_is_eligible_no_rules_defaults_true():
    ctx = _ctx([])
    assert ctx.rules.is_eligible(ctx, "agent_0") is True


def test_every_rule_is_eligible_still_runs_after_a_veto():
    _CountsCalls.call_count = 0
    ctx = _ctx([_NeverEligible(key="veto", params={}), _CountsCalls(key="counter", params={})])
    ctx.rules.is_eligible(ctx, "agent_0")
    assert _CountsCalls.call_count == 1


def test_ineligibility_note_falls_back_to_generic_when_rules_say_nothing():
    ctx = _ctx([_NeverEligible(key="veto", params={})])
    note = ctx.rules.ineligibility_note(ctx, "agent_0")
    assert note == "Something about the community's current rules held you back this round."


def test_ineligibility_note_prefers_a_rules_own_description():
    class _NeverEligibleWithReason(Rule):
        type_name = "_never_eligible_reason"

        def is_eligible(self, ctx, agent_id):
            return False

        def describe(self, ctx, agent_id):
            return "You are banned."

    ctx = _ctx([_NeverEligibleWithReason(key="veto", params={})])
    assert ctx.rules.ineligibility_note(ctx, "agent_0") == "You are banned."
