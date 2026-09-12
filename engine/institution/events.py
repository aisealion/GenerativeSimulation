# The generic event model for the institution kernel — always a
# point-in-time occurrence (an object mutation, a one-off announcement),
# never an interval. An interval fact with a genuine duration (a role, a
# ban, norm_active) has a different access pattern ("who holds this right
# now") that this model was never a good fit for and doesn't try to
# cover — that stays exactly what it always was, a direct call to
# roles.roles.set_fact()/end_fact() (see actions/handlers/harvest.py's
# "dead" fact for the pattern). This file is what closes the real gap
# those two primitives left: a one-off occurrence visible to more than one
# agent but not literally everyone (this round's participants, whoever
# currently holds a role, an explicit list) had no native representation
# before this — event_sink.py's first cut faked it by writing one
# duplicate roles.roles fact per resolved agent, which worked but stored
# N copies of what was really one occurrence. Events are stored instead in
# state/events.json — one record per occurrence, with its own resolved
# `visible_to`, read by whoever needs "what happened this round that this
# agent should know" (engine.llm_agents.render_notices()) or "who should
# remember this" (this file's own event_memory_specs()).

from dataclasses import dataclass, field
from enum import Enum


class Visibility(Enum):
    GLOBAL = "global"              # every agent, always
    PARTICIPANTS = "participants"  # this round's participants in the emitting action
    ROLE_HOLDERS = "role_holders"  # whoever currently holds `role`
    AGENT = "agent"                # exactly one agent (`holder`)
    AGENT_SET = "agent_set"        # an explicit list of agent_ids (`agents`)


@dataclass
class Event:
    """One institutional occurrence, always narrated (`text` is required —
    an event with nothing to say has no reason to exist as one; a silent
    state mutation just mutates state directly). `holder`/`role`/`agents`
    are only consulted for the matching `visibility` value; irrelevant for
    any other."""

    event_type: str
    text: str
    visibility: Visibility = Visibility.GLOBAL
    holder: str = "community"                     # used when visibility is AGENT (or GLOBAL, for the record's own framing)
    role: str | None = None                       # required when visibility is ROLE_HOLDERS
    agents: list = field(default_factory=list)    # required when visibility is AGENT_SET


class EventEmitter:
    """`ctx.events` / `context.objects`'s own emitter — resolves each
    Event's `visibility` into a concrete `visible_to` (a list of
    agent_ids, or None for GLOBAL) and appends exactly one record to
    `state["events"]`. Never touches roles.roles — an Event is never a
    fact with a duration, so there's nothing for set_fact()/end_fact() to
    do here."""

    def __init__(self, events, fluents, round_number, participants=()):
        self._events = events
        self._fluents = fluents
        self._round_number = round_number
        self._participants = participants

    def emit(self, event):
        self._events.append({
            "event_type": event.event_type,
            "text": event.text,
            "round": self._round_number,
            "visibility": event.visibility.value,
            "visible_to": self._resolve_visible_to(event),
        })

    def _resolve_visible_to(self, event):
        if event.visibility == Visibility.GLOBAL:
            return None
        if event.visibility == Visibility.AGENT:
            return [event.holder]
        if event.visibility == Visibility.AGENT_SET:
            return list(event.agents)
        if event.visibility == Visibility.PARTICIPANTS:
            return list(self._participants)
        if event.visibility == Visibility.ROLE_HOLDERS:
            from roles.roles import current_holder
            if event.role is None:
                raise ValueError("Event(visibility=ROLE_HOLDERS) requires `role` to be set")
            holder = current_holder(self._fluents, event.role, self._round_number)
            return [holder] if holder else []
        raise ValueError(f"unknown visibility {event.visibility!r}")


def visible_events(events, agent_id, round_number):
    """Every event from exactly this round visible to `agent_id` — unlike
    roles.roles.visible_facts(), there's no "currently open" case to
    consider, since every event is a point occurrence: it's relevant for
    the one round it happened and never again. Feeds
    engine.llm_agents.render_notices() alongside the existing
    fact-visibility path."""
    return [
        record for record in events
        if record["round"] == round_number
        and (record["visible_to"] is None or agent_id in record["visible_to"])
    ]


def event_memory_specs(events, round_number):
    """Memory-episode specs for every event from exactly this round —
    mirrors roles.roles.fact_memory_events()'s own {event_type, text,
    agent_id, group_id} shape. A GLOBAL event (visible_to=None) becomes
    one spec in the shared "community" group; anything else becomes one
    spec per resolved agent, each in that agent's own private group —
    deliberately not deduplicated into a single shared write, since a
    restricted-audience event genuinely shouldn't be recallable from a
    non-participant's own memory."""
    specs = []
    for record in events:
        if record["round"] != round_number:
            continue
        if record["visible_to"] is None:
            specs.append({
                "event_type": record["event_type"], "text": record["text"],
                "agent_id": None, "group_id": "community",
            })
        else:
            for agent_id in record["visible_to"]:
                specs.append({
                    "event_type": record["event_type"], "text": record["text"],
                    "agent_id": agent_id, "group_id": agent_id,
                })
    return specs
