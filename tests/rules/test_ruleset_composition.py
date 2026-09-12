from engine.institution.context import ActionContext
from engine.institution.rules import Rule, RuleSet


class _TrimByOne(Rule):
    """Stub: always trims 1kg off whatever it's handed, no note."""
    type_name = "_trim_by_one"

    def after_agent(self, ctx, agent_id, record_entry):
        return {"harvested_kg": record_entry["harvested_kg"] - 1}


class _ViolateIfOver(Rule):
    """Stub: trims anything over its configured limit, with a note."""
    type_name = "_violate_if_over"

    def after_agent(self, ctx, agent_id, record_entry):
        limit = self.params["limit"]
        if record_entry["harvested_kg"] <= limit:
            return None
        return {"harvested_kg": limit, "note": "trimmed by stub"}


class _RecordsSettled(Rule):
    """Stub: records what on_agent_settled() was called with, for
    assertion — the fully-settled value, after every other rule's own
    after_agent() patch has already been applied."""
    type_name = "_records_settled"
    calls = []

    def after_agent(self, ctx, agent_id, record_entry):
        return {"harvested_kg": record_entry["harvested_kg"] - 100}  # obviously-intermediate value

    def on_agent_settled(self, ctx, agent_id, record_entry):
        _RecordsSettled.calls.append((agent_id, record_entry["harvested_kg"]))


def _ctx(rules):
    state = {
        "config": {"rules": {"_test_action": []}}, "fluents": [], "runtime": {"stock_kg": 100.0},
        "agents": {}, "round_number": 1,
    }
    ctx = ActionContext.build({"name": "_test_action"}, state, 1)
    ctx.rules = RuleSet(rules)
    return ctx


def _entry(kg=10.0):
    return {"harvested_kg": kg}


def test_apply_after_agent_threads_the_patch_through_rules_in_order():
    ctx = _ctx([_TrimByOne(key="a", params={}), _TrimByOne(key="b", params={})])
    entry = _entry(10.0)
    ctx.rules.apply_after_agent(ctx, "agent_0", entry)
    assert entry["harvested_kg"] == 8.0


def test_apply_after_agent_concatenates_notes_from_every_contributing_rule():
    n1 = _ViolateIfOver(key="n1", params={"limit": 100})  # never triggers
    n2 = _ViolateIfOver(key="n2", params={"limit": 5})    # triggers
    ctx = _ctx([n1, n2])
    entry = _entry(10.0)
    ctx.rules.apply_after_agent(ctx, "agent_0", entry)
    assert entry["note"] == "trimmed by stub"


def test_apply_after_agent_is_last_patch_wins_for_non_note_fields():
    """Unlike "note" (which concatenates), any other field a later rule's
    patch touches simply overwrites what an earlier rule already set —
    deliberately simpler than the old NormDecision's "first sanction
    wins" special case, which was a harvest-specific convention that
    didn't generalize to an arbitrary field."""
    n1 = _ViolateIfOver(key="n1", params={"limit": 1})
    n2 = _ViolateIfOver(key="n2", params={"limit": 1})
    ctx = _ctx([n1, n2])
    entry = _entry(10.0)
    ctx.rules.apply_after_agent(ctx, "agent_0", entry)
    assert entry["harvested_kg"] == 1  # n2's patch is what's left, both trimmed to the same limit


def test_on_agent_settled_sees_the_fully_patched_value_not_the_intermediate_one():
    _RecordsSettled.calls.clear()
    stub = _RecordsSettled(key="records", params={})
    ctx = _ctx([_TrimByOne(key="trim", params={}), stub])
    entry = _entry(10.0)
    ctx.rules.apply_after_agent(ctx, "agent_0", entry)
    ctx.rules.settle_agent(ctx, "agent_0", entry)
    assert _RecordsSettled.calls == [("agent_0", entry["harvested_kg"])]
    assert entry["harvested_kg"] == 10.0 - 1 - 100


def test_describe_constraints_joins_only_non_none():
    class _Silent(Rule):
        type_name = "_silent"

    class _Speaks(Rule):
        type_name = "_speaks"

        def describe(self, ctx, agent_id):
            return "hello"

    ctx = _ctx([_Silent(key="s", params={}), _Speaks(key="sp", params={})])
    assert ctx.rules.describe_constraints(ctx, "agent_0") == "hello"


def test_no_rules_is_a_pure_passthrough():
    ctx = _ctx([])
    entry = _entry(10.0)
    ctx.rules.apply_after_agent(ctx, "agent_0", entry)
    assert entry == {"harvested_kg": 10.0}
