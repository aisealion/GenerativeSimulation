def role_holder(role_name, agent_id, fluents, round_number):
    for record in fluents:
        if (
            record["fluent"] == role_name
            and record["holder"] == agent_id
            and record["initiated_round"] <= round_number
            and (record["terminated_round"] is None or record["terminated_round"] > round_number)
        ):
            return record
    return None


def set_fact(
    fluents, fluent_name, args, holder, round_number,
    narration=None, visibility="agent_only", event_type="fact_initiated",
):
    """General-purpose fluent write: terminate any open record for this
    exact (fluent_name, args) pair, then open a new one. assign_role() is
    the role-shaped special case of this (see below); use this directly for
    non-role facts — an obligation, a sanction, a status a norm wants
    tracked — where `holder` may be an individual agent_id or the sentinel
    "community" for a fact that isn't about one specific agent.

    `narration` is optional, already in-world-phrased plain language
    (the same convention phases/*.py's memory_writes() already uses for its
    `text` field) describing this fact for whoever it's visible to. A
    record with no narration renders nowhere — it's plumbing only (this is
    how plain role_fluent records, like the "fisher" role every agent
    holds, stay invisible to the notice renderer without needing a
    migration). `visibility` is `"public"` (surfaced to every agent) or
    `"agent_only"` (surfaced only when `holder` matches the requesting
    agent) — only meaningful when `narration` is set. Default to
    `"public"` for anything a community norm would plausibly want logged or
    monitored (this project's own adopted norms consistently call for
    public ledgers/monitors); use `"agent_only"` for something between one
    agent and the mechanism, like an individual warning.

    Whenever `narration` is set, the same text also reaches the memory
    layer automatically (see `fact_memory_events()` below) — `event_type`
    picks which of `engine/memory/write.py`'s `IMPORTANCE_BY_EVENT_TYPE`
    entries it's logged under; the generic `"fact_initiated"` default is
    fine unless a more specific existing type applies (e.g.
    `"graduated_sanction_applied"` for a real sanction).
    """
    for record in fluents:
        if (
            record["fluent"] == fluent_name
            and record["args"] == args
            and record["terminated_round"] is None
        ):
            record["terminated_round"] = round_number
    record = {
        "fluent": fluent_name,
        "args": args,
        "holder": holder,
        "initiated_round": round_number,
        "terminated_round": None,
    }
    if narration is not None:
        record["narration"] = narration
        record["visibility"] = visibility
        record["event_type"] = event_type
    fluents.append(record)
    return fluents


def end_fact(
    fluents, fluent_name, args, round_number,
    narration=None, visibility=None, event_type="fact_ended",
):
    """Terminate the open record for (fluent_name, args), if any, without
    opening a replacement — e.g. a ban that's been served in full. Pass
    `narration` to describe the closing event itself (e.g. "Your ban has
    been lifted.") — same rules as `set_fact()`: reaches prompt (for
    exactly the round it closes, via `visible_facts()`) and memory
    automatically. `visibility` defaults to the record's own opening
    `visibility` if not given; only meaningful when `narration` is set."""
    for record in fluents:
        if (
            record["fluent"] == fluent_name
            and record["args"] == args
            and record["terminated_round"] is None
        ):
            record["terminated_round"] = round_number
            if narration is not None:
                record["end_narration"] = narration
                record["end_visibility"] = (
                    visibility if visibility is not None else record.get("visibility", "agent_only")
                )
                record["end_event_type"] = event_type
    return fluents


def _visible_to(agent_id, holder, visibility):
    return visibility == "public" or holder == agent_id


def visible_facts(fluents, agent_id, round_number):
    """Every fluent record with something narrated for right now and
    visible to agent_id — either public, or held by agent_id itself. Two
    cases: a currently-holdsAt record's opening `narration` (visible for
    as long as the fact stays open), and a record that closed exactly this
    round, surfaced via its `end_narration` for that one round only (the
    two are mutually exclusive per record: a record can't be both
    currently-open and closed-this-round). Used by the engine's prompt
    renderer to build an agent's "what's currently true" section; never
    interprets a raw value itself, only surfaces narration the mechanism
    that wrote the fact already authored."""
    results = []
    for record in fluents:
        if (
            record.get("narration")
            and _visible_to(agent_id, record["holder"], record.get("visibility"))
            and record["initiated_round"] <= round_number
            and (record["terminated_round"] is None or record["terminated_round"] > round_number)
        ):
            results.append(record)
        elif (
            record.get("terminated_round") == round_number
            and record.get("end_narration")
            and _visible_to(agent_id, record["holder"], record.get("end_visibility"))
        ):
            results.append({**record, "narration": record["end_narration"]})
    return results


def fact_memory_events(fluents, round_number):
    """Memory-episode specs for every fact newly opened or newly closed
    this exact round that carries narration — pure, no I/O (mirrors the
    shape `phases/*.py`'s `memory_writes()` already returns:
    `{event_type, text, agent_id, group_id}`). The caller
    (`engine/simulate.py`) turns these into actual `write_episode()` calls,
    once per round after all of that round's phases have run — not once
    per phase, since a fact set by an early phase would otherwise still
    read as "newly opened" to a later phase's own call and get logged
    twice."""
    events = []
    for record in fluents:
        if record.get("initiated_round") == round_number and record.get("narration"):
            events.append(_memory_spec(
                record["holder"], record.get("visibility", "agent_only"),
                record.get("event_type", "fact_initiated"), record["narration"],
            ))
        if record.get("terminated_round") == round_number and record.get("end_narration"):
            events.append(_memory_spec(
                record["holder"], record.get("end_visibility", "agent_only"),
                record.get("end_event_type", "fact_ended"), record["end_narration"],
            ))
    return events


def _memory_spec(holder, visibility, event_type, text):
    group_id = "community" if visibility == "public" else holder
    agent_id = None if holder == "community" else holder
    return {"event_type": event_type, "text": text, "agent_id": agent_id, "group_id": group_id}


def assign_role(role_name, agent_id, fluents, round_number, args=None):
    args = args if args is not None else [agent_id]
    return set_fact(fluents, role_name, args, agent_id, round_number)
