from engine.institution.context import ActionContext
from engine.institution.rules import Rule, RuleSet


class _RecordsRoundResults(Rule):
    type_name = "_records_round_results"
    seen = None

    def after_action(self, ctx, round_record):
        _RecordsRoundResults.seen = round_record


class _OverridesStock(Rule):
    """The old override_stock_after_regrowth() special method doesn't
    exist any more — a rule that needs to override the round's own final
    stock number just writes ctx.state["runtime"]["stock_kg"] and
    round_record["stock_kg_after_regrowth"] directly from its
    after_action() hook, since both are already in scope generically."""
    type_name = "_overrides_stock"

    def after_action(self, ctx, round_record):
        value = self.params["value"]
        ctx.state["runtime"]["stock_kg"] = value
        round_record["stock_kg_after_regrowth"] = value


def _ctx(rules, stock=100.0):
    state = {
        "config": {"rules": {"_test_action": []}}, "fluents": [],
        "runtime": {"stock_kg": stock}, "agents": {}, "round_number": 1,
    }
    ctx = ActionContext.build({"name": "_test_action"}, state, 1)
    ctx.rules = RuleSet(rules)
    return ctx


def test_after_action_receives_the_full_round_record():
    _RecordsRoundResults.seen = None
    ctx = _ctx([_RecordsRoundResults(key="r", params={})])
    round_record = {"agents": {"agent_0": {"effort": 0.5, "harvested_kg": 5.0}}}
    ctx.rules.after_action(ctx, round_record)
    assert _RecordsRoundResults.seen == round_record


def test_a_rule_can_override_the_round_stock_directly():
    ctx = _ctx([_OverridesStock(key="o", params={"value": 42.0})], stock=100.0)
    round_record = {"stock_kg_after_regrowth": 95.0}
    ctx.rules.after_action(ctx, round_record)
    assert ctx.state["runtime"]["stock_kg"] == 42.0
    assert round_record["stock_kg_after_regrowth"] == 42.0


def test_no_override_leaves_the_original_round_record_value_alone():
    ctx = _ctx([_RecordsRoundResults(key="r", params={})])
    round_record = {"stock_kg_after_regrowth": 95.0}
    ctx.rules.after_action(ctx, round_record)
    assert round_record["stock_kg_after_regrowth"] == 95.0


def test_last_rule_in_config_order_wins_when_two_both_override():
    ctx = _ctx([
        _OverridesStock(key="first", params={"value": 10.0}),
        _OverridesStock(key="second", params={"value": 20.0}),
    ])
    round_record = {"stock_kg_after_regrowth": 95.0}
    ctx.rules.after_action(ctx, round_record)
    assert ctx.state["runtime"]["stock_kg"] == 20.0
    assert round_record["stock_kg_after_regrowth"] == 20.0
