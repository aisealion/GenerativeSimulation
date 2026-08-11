# Reads: state/config.json, state/fluents.json, state/runtime.json (proposals).
# Writes: state/runtime.json (vote tallies), state/fluents.json (adopted rules).

from llm_agents import call_fisher_agent


def run(state):
    runtime = state["runtime"]
    agents = state["agents"]
    round_number = state["round_number"]
    agent_ids = list(agents.keys())

    last_propose = next(r for r in reversed(runtime["rounds"]) if r["phase"] == "propose")

    # Proposal A is always the first agent's, Proposal B the second's — this
    # fixed order also serves as the tie-break rule: A wins a 1-1 split.
    proposer_a, proposer_b = agent_ids[0], agent_ids[1]
    proposal_a = last_propose["proposals"][proposer_a]
    proposal_b = last_propose["proposals"][proposer_b]

    votes = {}
    for agent_id in agent_ids:
        response = call_fisher_agent(
            agent_id,
            round_number,
            "vote",
            proposal_a_policy=proposal_a["policy"],
            proposal_a_operationalization=proposal_a["operationalization"],
            proposal_b_policy=proposal_b["policy"],
            proposal_b_operationalization=proposal_b["operationalization"],
        )
        choice = str(response["vote"]).strip().upper()
        votes[agent_id] = {"vote": choice, "reasoning": response.get("reasoning", "")}

    votes_for_a = sum(1 for v in votes.values() if v["vote"] == "A")
    votes_for_b = sum(1 for v in votes.values() if v["vote"] == "B")
    winner = "A" if votes_for_a >= votes_for_b else "B"
    winning_proposal = proposal_a if winner == "A" else proposal_b
    winning_proposer = proposer_a if winner == "A" else proposer_b

    round_record = {
        "round": round_number,
        "phase": "vote",
        "votes": votes,
        "votes_for_a": votes_for_a,
        "votes_for_b": votes_for_b,
        "winner": winner,
        "winning_proposer": winning_proposer,
    }

    runtime["round"] = round_number
    runtime["rounds"].append(round_record)
    state["adopted_norm"] = winning_proposal
    return round_record
