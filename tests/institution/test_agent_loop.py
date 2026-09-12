import engine.institution.rules as rules_module
from engine.institution.agent_loop import default_ineligible_record, per_agent_decision
from engine.institution.context import ActionContext
from engine.institution.rules import Rule

ACTION = "_test_action"
AGENTS = {"agent_0": {"name": "Kai", "personality_traits": ""}, "agent_1": {"name": "Mara", "personality_traits": ""}}


def _state():
    return {
        "config": {"rules": {ACTION: []}},
        "fluents": [],
        "runtime": {"rounds": []},
        "agents": AGENTS,
        "round_number": 1,
    }


def _ctx(state, monkeypatch, rule_types=None):
    monkeypatch.setattr(rules_module, "discover_rule_types", lambda action_name: rule_types or {})
    return ActionContext.build({"name": ACTION}, state, state["round_number"])


def test_calls_every_participant_and_defaults_participated(monkeypatch):
    seen = []
    monkeypatch.setattr(
        "engine.institution.context.AgentCaller.call",
        lambda self, agent_id, **fields: seen.append((agent_id, fields)) or {"raw": agent_id},
    )
    ctx = _ctx(_state(), monkeypatch)

    records = per_agent_decision(
        ctx,
        build_fields=lambda agent_id: {"who": agent_id},
        build_record=lambda agent_id, response: {"echo": response["raw"]},
    )

    assert sorted(seen) == [("agent_0", {"who": "agent_0"}), ("agent_1", {"who": "agent_1"})]
    assert records == {
        "agent_0": {"echo": "agent_0", "participated": True},
        "agent_1": {"echo": "agent_1", "participated": True},
    }


def test_ineligible_agent_never_gets_called_and_uses_default_record(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "engine.institution.context.AgentCaller.call",
        lambda self, agent_id, **fields: calls.append(agent_id) or {},
    )

    class _Ban(Rule):
        type_name = "_ban"

        def is_eligible(self, ctx, agent_id):
            return agent_id != "agent_0"

        def describe(self, ctx, agent_id):
            return "You are currently banned." if agent_id == "agent_0" else None

    state = _state()
    state["config"]["rules"][ACTION] = [{"type": "_ban"}]
    ctx = _ctx(state, monkeypatch, rule_types={"_ban": _Ban})

    records = per_agent_decision(ctx, build_fields=lambda a: {}, build_record=lambda a, r: {})

    assert calls == ["agent_1"]
    assert records["agent_0"] == default_ineligible_record(ctx, "agent_0")
    assert records["agent_0"]["note"] == "You are currently banned."
    assert records["agent_1"] == {"participated": True}


def test_custom_ineligible_record_overrides_the_default(monkeypatch):
    class _Ban(Rule):
        type_name = "_ban"

        def is_eligible(self, ctx, agent_id):
            return False

    state = _state()
    state["config"]["rules"][ACTION] = [{"type": "_ban"}]
    monkeypatch.setattr(rules_module, "discover_rule_types", lambda action_name: {"_ban": _Ban})
    ctx = ActionContext.build({"name": ACTION}, state, state["round_number"])

    records = per_agent_decision(
        ctx, build_fields=lambda a: {}, build_record=lambda a, r: {},
        ineligible_record=lambda agent_id: {"participated": False, "custom": agent_id},
    )

    assert records["agent_0"] == {"participated": False, "custom": "agent_0"}


def test_after_settle_sees_the_rule_patched_record_not_the_raw_one(monkeypatch):
    monkeypatch.setattr("engine.institution.context.AgentCaller.call", lambda self, agent_id, **fields: {})

    class _Trim(Rule):
        type_name = "_trim"

        def after_agent(self, ctx, agent_id, record_entry):
            return {"amount": record_entry["amount"] - 1}

    state = _state()
    state["config"]["rules"][ACTION] = [{"type": "_trim"}]
    ctx = _ctx(state, monkeypatch, rule_types={"_trim": _Trim})

    seen_in_after_settle = {}
    per_agent_decision(
        ctx,
        build_fields=lambda a: {},
        build_record=lambda a, r: {"amount": 10},
        after_settle=lambda agent_id, record_entry: seen_in_after_settle.__setitem__(agent_id, record_entry["amount"]),
    )

    assert seen_in_after_settle == {"agent_0": 9, "agent_1": 9}


def test_settle_agent_hook_runs_after_after_settle_callback_is_wired_in_between(monkeypatch):
    """Confirms the actual call order per agent is
    apply_after_agent -> settle_agent -> after_settle, not some other
    interleaving — settle_agent must see the final patched record, and
    after_settle must run only once settle_agent has already had its turn."""
    monkeypatch.setattr("engine.institution.context.AgentCaller.call", lambda self, agent_id, **fields: {})
    order = []

    class _Tracker(Rule):
        type_name = "_tracker"

        def after_agent(self, ctx, agent_id, record_entry):
            order.append((agent_id, "after_agent"))
            return None

        def on_agent_settled(self, ctx, agent_id, record_entry):
            order.append((agent_id, "settle_agent"))

    state = _state()
    state["config"]["rules"][ACTION] = [{"type": "_tracker"}]
    ctx = _ctx(state, monkeypatch, rule_types={"_tracker": _Tracker})

    per_agent_decision(
        ctx, build_fields=lambda a: {}, build_record=lambda a, r: {},
        after_settle=lambda agent_id, record_entry: order.append((agent_id, "after_settle")),
    )

    assert order == [
        ("agent_0", "after_agent"), ("agent_0", "settle_agent"), ("agent_0", "after_settle"),
        ("agent_1", "after_agent"), ("agent_1", "settle_agent"), ("agent_1", "after_settle"),
    ]
