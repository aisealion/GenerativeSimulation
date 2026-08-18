"""Retrieval for prompt rendering — pre-fetched by driver code (see
llm_agents.render_relevant_memories), never exposed as a tool the fisher
agent calls itself.

graphiti.search() returns EntityEdge (extracted facts), which don't carry
back the event_type/importance of the episode(s) they came from — and
those two fields are exactly what prompts/memory_phrasing.py needs to
phrase a result safely. So both retrieval paths here query Episodic nodes
directly (via the fulltext index Graphiti already builds, and via the
event_type/importance properties memory/write.py patches on) rather than
going through graphiti.search()/retrieve_episodes() — this keeps a single
consistent record shape across the relevance and importance paths, which
matters since they get merged and deduplicated below.
"""
from memory.client import ensure_indices, graphiti, round_reference_time, run_async

PHASE_QUERY_TEMPLATES = {
    "harvest": [
        ("own_proposals", "proposals made by {agent}"),
        ("own_violations", "violations or missed obligations by {agent}"),
        ("community_compliance", "recent compliance trend across the community"),
    ],
    "discuss": [
        ("recent_proposals", "proposals raised in recent rounds"),
        ("unresolved_disputes", "disagreements not yet resolved"),
    ],
    "vote": [
        ("similar_past_votes", "past votes on structurally similar proposals"),
    ],
}

_RECORD_RETURN = """
    RETURN node.uuid AS uuid, node.content AS content, node.group_id AS group_id,
           node.event_type AS event_type, node.importance AS importance
"""


async def _search_relevance(query_text, group_ids, as_of, limit):
    if limit <= 0:
        return []
    records, _, _ = await graphiti.driver.execute_query(
        f"""
        CALL db.index.fulltext.queryNodes("episode_content", $query, {{limit: $overfetch}})
        YIELD node, score
        WHERE node.group_id IN $group_ids AND node.valid_at <= $as_of
        {_RECORD_RETURN}
        ORDER BY score DESC
        LIMIT $limit
        """,
        query=query_text,
        group_ids=group_ids,
        as_of=as_of,
        overfetch=limit * 5 + 10,
        limit=limit,
    )
    return [dict(r) for r in records]


async def _search_importance(group_ids, as_of, limit):
    if limit <= 0:
        return []
    records, _, _ = await graphiti.driver.execute_query(
        f"""
        MATCH (e:Episodic)
        WHERE e.group_id IN $group_ids AND e.importance IS NOT NULL AND e.valid_at <= $as_of
        WITH e AS node
        {_RECORD_RETURN}
        ORDER BY importance DESC
        LIMIT $limit
        """,
        group_ids=group_ids,
        as_of=as_of,
        limit=limit,
    )
    return [dict(r) for r in records]


async def _retrieve(agent_id, phase, round_num, top_k_relevance, top_k_importance):
    await ensure_indices()
    group_ids = [agent_id, "community"]
    as_of = round_reference_time(round_num)

    results = []
    for _label, template in PHASE_QUERY_TEMPLATES.get(phase, []):
        query_text = template.format(agent=agent_id)
        results.extend(await _search_relevance(query_text, group_ids, as_of, top_k_relevance))
    results.extend(await _search_importance(group_ids, as_of, top_k_importance))
    return results


def retrieve_memories(agent_id, phase, round_num, top_k_relevance=3, top_k_importance=2):
    records = run_async(_retrieve(agent_id, phase, round_num, top_k_relevance, top_k_importance))

    seen = set()
    deduped = []
    for record in records:
        if record["uuid"] in seen:
            continue
        seen.add(record["uuid"])
        deduped.append(record)
    return deduped
