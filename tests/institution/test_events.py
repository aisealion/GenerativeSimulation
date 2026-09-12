from roles.roles import assign_role
from engine.institution.events import Event, EventEmitter, Visibility, visible_events, event_memory_specs


def _emitter(events=None, fluents=None, round_number=1, participants=()):
    events = events if events is not None else []
    fluents = fluents if fluents is not None else []
    return EventEmitter(events, fluents, round_number, participants=participants), events, fluents


def test_global_event_is_visible_to_anyone_with_visible_to_none():
    emitter, events, _ = _emitter()
    emitter.emit(Event(event_type="object_mutated", text="Something happened.", visibility=Visibility.GLOBAL))

    assert events[0]["visible_to"] is None
    assert visible_events(events, "agent_9", 1)


def test_agent_event_is_visible_only_to_that_agent():
    emitter, events, _ = _emitter()
    emitter.emit(Event(event_type="object_mutated", text="You were warned.",
                        holder="agent_1", visibility=Visibility.AGENT))

    assert events[0]["visible_to"] == ["agent_1"]
    assert visible_events(events, "agent_1", 1)
    assert not visible_events(events, "agent_2", 1)


def test_agent_set_event_is_visible_to_every_named_agent():
    emitter, events, _ = _emitter()
    emitter.emit(Event(event_type="object_mutated", text="Selected for review.",
                        visibility=Visibility.AGENT_SET, agents=["agent_1", "agent_3"]))

    assert set(events[0]["visible_to"]) == {"agent_1", "agent_3"}
    assert visible_events(events, "agent_1", 1)
    assert visible_events(events, "agent_3", 1)
    assert not visible_events(events, "agent_2", 1)


def test_participants_event_resolves_against_the_emitting_action_participants():
    emitter, events, _ = _emitter(participants=["agent_5", "agent_6"])
    emitter.emit(Event(event_type="object_mutated", text="Round summary shared.",
                        visibility=Visibility.PARTICIPANTS))

    assert set(events[0]["visible_to"]) == {"agent_5", "agent_6"}
    assert visible_events(events, "agent_5", 1)
    assert not visible_events(events, "agent_7", 1)


def test_role_holders_event_resolves_the_current_holder():
    fluents = []
    assign_role("_test_treasurer", "agent_2", fluents, round_number=1, args=[])
    emitter, events, _ = _emitter(fluents=fluents)
    emitter.emit(Event(event_type="object_mutated", text="A treasurer-only notice.",
                        visibility=Visibility.ROLE_HOLDERS, role="_test_treasurer"))

    assert events[0]["visible_to"] == ["agent_2"]
    assert visible_events(events, "agent_2", 1)
    assert not visible_events(events, "agent_3", 1)


def test_role_holders_event_with_no_current_holder_is_visible_to_nobody():
    emitter, events, _ = _emitter()
    emitter.emit(Event(event_type="object_mutated", text="Should never appear.",
                        visibility=Visibility.ROLE_HOLDERS, role="_nobody_holds_this"))

    assert events[0]["visible_to"] == []
    assert visible_events(events, "agent_1", 1) == []


def test_role_holders_event_without_a_role_raises():
    import pytest
    emitter, events, _ = _emitter()
    with pytest.raises(ValueError, match="requires `role`"):
        emitter.emit(Event(event_type="object_mutated", text="x", visibility=Visibility.ROLE_HOLDERS))


def test_event_is_visible_only_for_its_own_round():
    emitter, events, _ = _emitter(round_number=3)
    emitter.emit(Event(event_type="object_mutated", text="A one-off announcement.", visibility=Visibility.GLOBAL))

    assert visible_events(events, "agent_1", 3)
    assert visible_events(events, "agent_1", 4) == []
    assert visible_events(events, "agent_1", 2) == []


def test_a_multi_agent_event_is_stored_exactly_once_not_duplicated():
    """The actual bug this redesign fixes: writing one duplicate fluent
    record per resolved agent used to store N copies of the same
    narration. An event is now stored once, with its resolved audience
    attached, regardless of how many agents can see it."""
    emitter, events, _ = _emitter(participants=["agent_1", "agent_2", "agent_3"])
    emitter.emit(Event(event_type="object_mutated", text="One occurrence.", visibility=Visibility.PARTICIPANTS))

    assert len(events) == 1


def test_event_memory_specs_for_a_global_event_writes_one_community_spec():
    events = [{"event_type": "object_mutated", "text": "x", "round": 2, "visibility": "global", "visible_to": None}]
    specs = event_memory_specs(events, round_number=2)
    assert specs == [{"event_type": "object_mutated", "text": "x", "agent_id": None, "group_id": "community"}]


def test_event_memory_specs_for_a_restricted_event_writes_one_spec_per_visible_agent():
    events = [{"event_type": "object_mutated", "text": "x", "round": 2, "visibility": "agent_set",
               "visible_to": ["agent_1", "agent_2"]}]
    specs = event_memory_specs(events, round_number=2)
    assert {s["agent_id"] for s in specs} == {"agent_1", "agent_2"}
    assert all(s["agent_id"] == s["group_id"] for s in specs)


def test_event_memory_specs_ignores_events_from_other_rounds():
    events = [{"event_type": "object_mutated", "text": "x", "round": 1, "visibility": "global", "visible_to": None}]
    assert event_memory_specs(events, round_number=2) == []
