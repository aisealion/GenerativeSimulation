# Reads: state/config.json, state/fluents.json, state/runtime.json (proposals).
# Writes: state/runtime.json (vote tallies), state/fluents.json (adopted rules).

from llm_agents import call_fisher_agent
from phases.base import Phase


class VotePhase(Phase):
    name = "vote"

    def _proposals(self, state):
        """Ordered (proposer_id, proposal) list, same order shown to every
        voter this round — built once so the numbering is consistent across
        all of them, and the tie-break below (max() over an in-order dict)
        favors whichever proposal comes first in this same order."""
        runtime = state["runtime"]
        agents = state["agents"]
        last_propose = next(r for r in reversed(runtime["rounds"]) if r["phase"] == "propose")
        return [(agent_id, last_propose["proposals"][agent_id]) for agent_id in agents]

    def prompt_fields(self, state, agent_id):
        proposals = self._proposals(state)
        proposals_block = "\n\n".join(
            f"{i}. Policy: {proposal['policy']}\n   In practice: {proposal['operationalization']}"
            for i, (_proposer_id, proposal) in enumerate(proposals, start=1)
        )
        return {"num_proposals": len(proposals), "proposals_block": proposals_block}

    def run(self, state):
        runtime = state["runtime"]
        agents = state["agents"]
        round_number = state["round_number"]
        agent_ids = list(agents.keys())

        proposals = self._proposals(state)

        votes = {}
        tally = {i: 0 for i in range(1, len(proposals) + 1)}
        for agent_id in agent_ids:
            response = call_fisher_agent(
                agent_id, round_number, "vote", **self.prompt_fields(state, agent_id)
            )
            choice = int(str(response["vote"]).strip())
            votes[agent_id] = {"vote": choice, "reasoning": response.get("reasoning", "")}
            tally[choice] += 1

        winner_index = max(tally, key=lambda i: tally[i])
        winning_proposer, winning_proposal = proposals[winner_index - 1]

        round_record = {
            "round": round_number,
            "phase": "vote",
            "votes": votes,
            "tally": tally,
            "winner_index": winner_index,
            "winning_proposer": winning_proposer,
        }

        runtime["round"] = round_number
        runtime["rounds"].append(round_record)
        state["adopted_norm"] = winning_proposal
        return round_record

    def memory_writes(self, state, round_record):
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


PHASE = VotePhase()
