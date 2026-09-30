"""ActionContext's real public surface (engine/institution/context.py) —
2026-09-28: a real round's custom actions/handlers/{name}.py called
ctx.action_spec and ctx.get_participating_agents(...), neither of which
exist. Neither compile-checking, institution-registration checking, nor
resolve_handler() (which only confirms run(ctx) is callable, never that
it uses ctx correctly) caught this — only actually invoking the handler
against a real ActionContext did, which
engine.simulate.norm_implementation_runtime_errors() now does for every
new action's own handler before a round can be committed. This test
documents the real attribute names directly, so the confusion is at
least checkable in isolation, not just discoverable by crashing live."""
import pytest

from engine.institution.context import ActionContext


def _ctx():
    state = {
        "config": {}, "fluents": [],
        "runtime": {"stock_kg": 300.0, "rounds": [], "objects": {}, "payoff": {}},
        "agents": {"agent_0": {"name": "Kai", "personality_traits": ""}},
        "object_types": {}, "objects": [], "round_number": 1,
    }
    spec = {"name": "test_action", "participation": {"policy": "all_alive_fishers"}}
    return ActionContext.build(spec, state, 1)


def test_the_actions_own_spec_is_dot_spec_not_dot_action_spec():
    ctx = _ctx()
    assert ctx.spec["name"] == "test_action"
    assert not hasattr(ctx, "action_spec")


def test_participants_are_already_resolved_not_a_method_to_call():
    ctx = _ctx()
    assert ctx.participants == ["agent_0"]
    assert not hasattr(ctx, "get_participating_agents")


def test_the_real_public_surface_a_custom_handler_can_rely_on():
    ctx = _ctx()
    for attr in ("spec", "state", "round_number", "participants", "agents", "events", "objects", "rules"):
        assert hasattr(ctx, attr), f"ActionContext is missing its own documented .{attr}"


def test_a_handler_calling_a_nonexistent_attribute_fails_loudly():
    def _buggy_handler(ctx):
        return ctx.action_spec["participation"]["policy"]

    with pytest.raises(AttributeError):
        _buggy_handler(_ctx())


def test_agent_id_as_a_prompt_field_name_fails_with_a_clear_message_not_a_bare_typeerror():
    # A real round's prompt.fields declared a field named "agent_id" on
    # every one of 9 new actions -- all failed identically with a bare
    # "call() got multiple values for argument 'agent_id'" TypeError
    # (fields is splatted as **kwargs alongside the positional agent_id
    # already on AgentCaller.call()), giving no hint at the actual,
    # one-line fix. This asserts the collision is now caught explicitly,
    # with a message that names the real cause.
    ctx = _ctx()
    with pytest.raises(ValueError, match="agent_id"):
        ctx.agents.call("agent_0", agent_id="agent_0", reasoning="...")
