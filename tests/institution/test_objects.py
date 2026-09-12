import pytest

from roles.roles import assign_role
from engine.institution.events import EventEmitter, visible_events
import engine.institution.objects as objects_module
from engine.institution.objects import ObjectRuntime, ObjectPermissionError

POOL_TYPE = {
    "type_name": "_test_pool",
    "fields": {"balance_kg": {"type": "number", "default": 0.0}},
    "operations": ["deposit", "withdraw", "read"],
    "permissions": {
        "WRITE": {"who": "ROLE:_test_treasurer"},
        "READ": {"who": "ALL"},
    },
    "visibility": {
        "balance_kg": {"who": "ALL"},
    },
}

SECRET_TYPE = {
    "type_name": "_test_secret_ledger",
    "fields": {"entries": {"type": "list", "default": []}},
    "operations": ["append", "read"],
    "permissions": {
        "APPEND": {"who": "ALL"},
        "READ": {"who": "ROLE:_test_treasurer"},
    },
    "visibility": {
        "entries": {"who": "ROLE:_test_treasurer"},
    },
}

LOCKED_TYPE = {
    "type_name": "_test_locked",
    "fields": {"value": {"type": "number", "default": 0}},
    "operations": ["set"],
    "permissions": {"WRITE": {"who": "NONE"}},
    "visibility": {"value": {"who": "NONE"}},
}


def _runtime(object_types, declarations, fluents=None, round_number=1, participants=(), runtime_objects=None):
    fluents = fluents if fluents is not None else []
    runtime_objects = runtime_objects if runtime_objects is not None else {}
    events = []
    emitter = EventEmitter(events, fluents, round_number, participants=participants)
    return ObjectRuntime(object_types, declarations, runtime_objects, fluents, round_number, emitter), fluents, events


def test_deposit_and_withdraw_adjust_balance_seeded_from_the_type_default():
    declarations = [{"id": "reserve", "type": "_test_pool"}]
    fluents = []
    assign_role("_test_treasurer", "agent_1", fluents, round_number=1, args=[])
    runtime, _, _events = _runtime({"_test_pool": POOL_TYPE}, declarations, fluents=fluents)

    # Nothing pre-seeded in runtime_objects — the field default (0.0) is
    # applied lazily on first touch, never something a declaration itself
    # carries.
    runtime.deposit("reserve", "balance_kg", 12.0, by_agent_id="agent_1")
    assert runtime.runtime_objects["reserve"]["fields"]["balance_kg"] == 12.0

    runtime.withdraw("reserve", "balance_kg", 5.0, by_agent_id="agent_1")
    assert runtime.runtime_objects["reserve"]["fields"]["balance_kg"] == 7.0


def test_declaration_never_needs_to_carry_field_values():
    """state/objects.json entries are declarations only ({"id", "type"}) —
    exactly like state/config.json's own norms entries, never the mutable
    state a norm/object accumulates at runtime."""
    declarations = [{"id": "reserve", "type": "_test_pool"}]
    assert "fields" not in declarations[0]


def test_role_gated_write_denied_to_a_non_holder():
    declarations = [{"id": "reserve", "type": "_test_pool"}]
    fluents = []
    assign_role("_test_treasurer", "agent_1", fluents, round_number=1, args=[])
    runtime, _, _events = _runtime({"_test_pool": POOL_TYPE}, declarations, fluents=fluents)

    with pytest.raises(ObjectPermissionError, match="_test_treasurer"):
        runtime.deposit("reserve", "balance_kg", 12.0, by_agent_id="agent_2")


def test_permission_who_none_always_denies():
    declarations = [{"id": "vault", "type": "_test_locked"}]
    runtime, _, _events = _runtime({"_test_locked": LOCKED_TYPE}, declarations)

    with pytest.raises(ObjectPermissionError, match="never permitted"):
        runtime.set("vault", "value", 5, by_agent_id="agent_1")


def test_append_and_read_on_a_role_gated_field():
    declarations = [{"id": "ledger", "type": "_test_secret_ledger"}]
    fluents = []
    assign_role("_test_treasurer", "agent_1", fluents, round_number=1, args=[])
    runtime, _, _events = _runtime({"_test_secret_ledger": SECRET_TYPE}, declarations, fluents=fluents)

    runtime.append("ledger", "entries", "agent_3 deposited 4kg", by_agent_id="agent_3")
    assert runtime.runtime_objects["ledger"]["fields"]["entries"] == ["agent_3 deposited 4kg"]

    assert runtime.read("ledger", "entries", viewer_agent_id="agent_1") == ["agent_3 deposited 4kg"]
    assert runtime.read("ledger", "entries", viewer_agent_id="agent_3") is None


def test_read_returns_none_for_a_who_none_field_without_raising():
    declarations = [{"id": "vault", "type": "_test_locked"}]
    runtime, _, _events = _runtime({"_test_locked": LOCKED_TYPE}, declarations)
    assert runtime.read("vault", "value", viewer_agent_id="agent_1") is None


def test_narration_emits_an_event_visible_this_round_only():
    declarations = [{"id": "reserve", "type": "_test_pool"}]
    fluents = []
    assign_role("_test_treasurer", "agent_1", fluents, round_number=4, args=[])
    runtime, _, events = _runtime({"_test_pool": POOL_TYPE}, declarations, fluents=fluents, round_number=4)

    runtime.deposit("reserve", "balance_kg", 8.0, by_agent_id="agent_1",
                     narration="The communal reserve grew by 8kg.")

    visible_now = visible_events(events, "agent_2", 4)
    assert any(e["text"] == "The communal reserve grew by 8kg." for e in visible_now)
    assert visible_events(events, "agent_2", 5) == []


def test_deposit_with_no_narration_emits_no_event():
    declarations = [{"id": "reserve", "type": "_test_pool"}]
    fluents = []
    assign_role("_test_treasurer", "agent_1", fluents, round_number=1, args=[])
    runtime, _, events = _runtime({"_test_pool": POOL_TYPE}, declarations, fluents=fluents)

    runtime.deposit("reserve", "balance_kg", 8.0, by_agent_id="agent_1")

    assert events == []


def test_unknown_object_id_raises_keyerror():
    runtime, _, _events = _runtime({"_test_pool": POOL_TYPE}, [])
    with pytest.raises(KeyError):
        runtime.deposit("nonexistent", "balance_kg", 1.0, by_agent_id="agent_1")


def test_custom_handler_dispatch(monkeypatch):
    """objects/handlers/ ships empty by design (same principle as norms/),
    so this exercises the dispatch mechanism against a monkeypatched
    handler map rather than a real file on disk — the same pattern
    tests/norms/test_registry.py already uses for NORM_TYPES."""
    calls = []

    def _fake_split(*, object_id, operation, by_agent_id, **kwargs):
        calls.append((object_id, operation, by_agent_id, kwargs))
        return "handled"

    monkeypatch.setattr(
        objects_module, "discover_handlers",
        lambda package: {"_test_splitter": lambda runtime, object_id, operation, by_agent_id=None, **kw:
                          _fake_split(object_id=object_id, operation=operation,
                                      by_agent_id=by_agent_id, **kw)},
    )

    custom_type = {**POOL_TYPE, "type_name": "_test_custom", "custom_handler": "_test_splitter"}
    declarations = [{"id": "reserve", "type": "_test_custom"}]
    runtime, _, _events = _runtime({"_test_custom": custom_type}, declarations)

    result = runtime.custom("reserve", "split", by_agent_id="agent_1", ratio=0.5)

    assert result == "handled"
    assert calls == [("reserve", "split", "agent_1", {"ratio": 0.5})]


def test_custom_handler_missing_declaration_raises():
    declarations = [{"id": "reserve", "type": "_test_pool"}]
    runtime, _, _events = _runtime({"_test_pool": POOL_TYPE}, declarations)
    with pytest.raises(ValueError, match="declares no custom_handler"):
        runtime.custom("reserve", "split", by_agent_id="agent_1")
