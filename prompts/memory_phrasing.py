"""Fourth-wall boundary for memory records — extends the convention
prompts/phrasing_map.json already established (internal names never appear
in rendered text directly, only their mapped phrasing does), for the one
case a static JSON map can't handle: a memory record's phrasing needs to
wrap dynamic text, not just substitute a fixed string.

Callers of memory.write.write_episode() are expected to pass already
in-world-phrased text as the episode body (see memory/write.py) — the
frame sentences below only add the temporal/social framing around it, they
don't synthesize content from raw internal fields.
"""
from memory.write import IMPORTANCE_BY_EVENT_TYPE

_FRAMES = {
    "role_fluent_initiated": "A while back, {text}",
    "periodic_check_triggered": "During a routine check, {text}",
    "threshold_obligation_triggered": "At one point, {text}",
    "reporting_violation": "A little while back, {text}",
    "graduated_sanction_applied": "You once faced a real consequence for it: {text}",
    "new_phase_activated": "At one point, how things are done around here changed: {text}",
    "vote_outcome": "The community decided: {text}",
    "proposal_made": "You once proposed: {text}",
    "routine_harvest": "{text}",
}

_missing = set(IMPORTANCE_BY_EVENT_TYPE) - set(_FRAMES)
if _missing:
    raise RuntimeError(
        f"prompts/memory_phrasing.py is missing a phrasing case for: {sorted(_missing)} "
        f"— add one before these event types can safely reach a rendered prompt"
    )


def phrase_memory(record):
    event_type = record.get("event_type")
    if event_type not in _FRAMES:
        raise ValueError(
            f"no phrasing case for memory event_type {event_type!r} — add one to "
            f"prompts/memory_phrasing.py before this can render in a prompt"
        )
    text = (record.get("content") or "").strip()
    return _FRAMES[event_type].format(text=text)
