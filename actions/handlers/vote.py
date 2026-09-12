from engine.institution.agent_loop import per_agent_decision
from engine.physics import alive_agent_ids


def proposals_for_round(state):
    """Ordered (proposer_id, proposal) list, same order shown to every
    voter this round. Prefers this round's actions/handlers/critique.py
    output (the critique-then-revise loop's final, possibly-revised text)
    over propose's own raw proposals — falls back to propose's when no
    critique round record exists for this round, so an older
    state/schedule.json with critique gated off (or a round resumed from
    before that action existed) still works unchanged.

    A module-level function, not tucked inside run(), because
    tests exercise it directly — same reason the old actions/vote.py kept
    it as its own method rather than folding it into setup()."""
    runtime = state["runtime"]
    agents = state["agents"]
    round_number = state["round_number"]
    critique_record = next(
        (r for r in runtime["rounds"] if r["round"] == round_number and r["action"] == "critique"),
        None,
    )
    if critique_record is not None:
        proposals_source = critique_record["proposals"]
    else:
        last_propose = next(r for r in reversed(runtime["rounds"]) if r["action"] == "propose")
        proposals_source = last_propose["proposals"]
    return [
        (agent_id, proposal) for agent_id, proposal in (
            (agent_id, proposals_source.get(agent_id, {})) for agent_id in alive_agent_ids(agents, runtime)
        )
        if "policy" in proposal
    ]


def run(ctx):
    state = ctx.state
    proposals = proposals_for_round(state)
    proposals_block = "\n\n".join(
        f"{i}. Policy: {proposal['policy']}\n   In practice: {proposal['operationalization']}"
        for i, (_proposer_id, proposal) in enumerate(proposals, start=1)
    )
    fields = {"num_proposals": len(proposals), "proposals_block": proposals_block}

    def build_record(agent_id, response):
        choice = int(str(response["vote"]).strip())
        return {"vote": choice, "reasoning": response.get("reasoning", "")}

    votes = per_agent_decision(ctx, lambda agent_id: fields, build_record)

    tally = {i: 0 for i in range(1, len(proposals) + 1)}
    for record in votes.values():
        if record.get("participated", True) and "vote" in record:
            tally[record["vote"]] += 1

    winner_index = max(tally, key=lambda i: tally[i])
    winning_proposer, winning_proposal = proposals[winner_index - 1]
    state["adopted_norm"] = winning_proposal

    return {
        "votes": votes,
        "tally": tally,
        "winner_index": winner_index,
        "winning_proposer": winning_proposer,
    }


def memory_writes(state, round_record):
    adopted = state.get("adopted_norm")
    if not adopted:
        return []
    winner_votes = round_record["tally"][round_record["winner_index"]]
    total_votes = sum(round_record["tally"].values())
    text = (
        f"the community voted (winning proposal took {winner_votes} of {total_votes} votes) "
        f"and adopted: {adopted['policy']}"
    )
    return [{"event_type": "vote_outcome", "text": text, "agent_id": None, "group_id": "community"}]
