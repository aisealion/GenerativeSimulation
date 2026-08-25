"""Episode writes to the shared Graphiti memory.

Callers (a Phase's memory_writes() hook) supply already in-world-phrased
text — CLAUDE.md's fourth-wall rule applies to anything that can end up in
a rendered prompt, and a memory record written now can surface in a prompt
many rounds later via prompts/memory_phrasing.py.
"""
from graphiti_core.nodes import EpisodeType

from engine.memory.client import ensure_indices, graphiti, round_reference_time, run_async

# Seeded from the norm-implementer's six templates (Step 1 of
# .claude/agents/norm-implementer.md / .opencode/agent/norm-implementer.md:
# role_fluent, periodic_check, threshold_obligation, reporting_obligation,
# graduated_sanction, new_phase) plus the events that already occur every
# game today (vote_outcome, proposal_made, routine_harvest). Scores 1-10 —
# starting values, tune later.
IMPORTANCE_BY_EVENT_TYPE = {
    "role_fluent_initiated": 4,
    "periodic_check_triggered": 5,
    "threshold_obligation_triggered": 8,
    "reporting_violation": 7,
    "graduated_sanction_applied": 9,
    "new_phase_activated": 5,
    "vote_outcome": 6,
    "proposal_made": 3,
    "routine_harvest": 1,
    # Generic fallback for mechanisms.roles.set_fact()/end_fact() calls that
    # don't specify a more specific type above — same importance band as
    # vote_outcome/new_phase_activated since these cover a genuine mix of
    # severities (a sanction vs. a minor status change) that a single
    # generic type can't score more precisely than that.
    "fact_initiated": 9,
    "fact_ended": 9,
}


async def _write_episode(event_type, text, round_num, agent_id, group_id, importance):
    await ensure_indices()
    result = await graphiti.add_episode(
        name=f"{event_type}_r{round_num}_{agent_id or group_id}",
        episode_body=text,
        source=EpisodeType.text,
        source_description=event_type,
        reference_time=round_reference_time(round_num),
        group_id=group_id,
    )
    # add_episode() has no metadata parameter, and EpisodicNode.episode_metadata
    # isn't actually persisted by EpisodicNode.save() in graphiti-core 0.29 (checked
    # the installed library source directly — the field exists on the model but
    # save() doesn't include it in the write). Patch event_type/importance on as
    # plain node properties instead, so query.py can filter/sort on them directly.
    await graphiti.driver.execute_query(
        "MATCH (e:Episodic {uuid: $uuid}) SET e.event_type = $event_type, e.importance = $importance",
        uuid=result.episode.uuid,
        event_type=event_type,
        importance=importance,
    )
    return result.episode.uuid


def write_episode(event_type, text, round_num, agent_id, group_id, importance=None):
    if event_type not in IMPORTANCE_BY_EVENT_TYPE:
        raise ValueError(
            f"unknown event_type {event_type!r} — add it to IMPORTANCE_BY_EVENT_TYPE "
            f"in memory/write.py (and a phrasing case in prompts/memory_phrasing.py) first"
        )
    if importance is None:
        importance = IMPORTANCE_BY_EVENT_TYPE[event_type]
    return run_async(_write_episode(event_type, text, round_num, agent_id, group_id, importance))
