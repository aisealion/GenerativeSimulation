# Reads: state/config.json, state/fluents.json, state/runtime.json
# (proposals — this round's critique-refined ones when present, propose's
# raw ones otherwise).
# Writes: state/runtime.json (vote tallies), state/fluents.json (adopted rules).

from engine.llm_agents import call_fisher_agent
from engine.action_base import SimpleAgentAction
from engine.physics import alive_agent_ids


class VoteAction(SimpleAgentAction):
    name = "vote"

    def _proposals(self, state):
        """Ordered (proposer_id, proposal) list, same order shown to every
        voter this round — built once so the numbering is consistent across
        all of them, and the tie-break below (max() over an in-order dict)
        favors whichever proposal comes first in this same order.

        Prefers this round's actions/critique.py output (the
        critique-then-revise loop's final, possibly-revised text) over
        propose's own raw proposals — falls back to propose's when no
        critique round record exists for this round, so an older
        state/schedule.json with critique gated off (or a round resumed from
        before this action existed) still works unchanged.

        Kept as its own public method (not folded into setup()) because
        tests/regression/test_critique_action.py calls this directly."""
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
            (agent_id, proposals_source[agent_id])
            for agent_id in alive_agent_ids(agents, runtime)
        ]

    def setup(self, state):
        """Hoists the previously-per-agent _proposals() call to once per
        round — the ballot doesn't change while votes are being cast."""
        return self._proposals(state)

    def build_fields(self, state, setup_ctx, agent_id):
        proposals = setup_ctx
        proposals_block = "\n\n".join(
            f"{i}. Policy: {proposal['policy']}\n   In practice: {proposal['operationalization']}"
            for i, (_proposer_id, proposal) in enumerate(proposals, start=1)
        )
        return {"num_proposals": len(proposals), "proposals_block": proposals_block}

    def call_agent(self, agent_id, round_number, fields):
        return call_fisher_agent(agent_id, round_number, self.name, **fields)

    def record_result(self, state, setup_ctx, agent_id, response):
        choice = int(str(response["vote"]).strip())
        return {"vote": choice, "reasoning": response.get("reasoning", "")}

    def per_agent_key(self):
        return "votes"

    def after_participants(self, state, setup_ctx, agent_records):
        proposals = setup_ctx
        tally = {i: 0 for i in range(1, len(proposals) + 1)}
        for record in agent_records.values():
            tally[record["vote"]] += 1

        winner_index = max(tally, key=lambda i: tally[i])
        winning_proposer, winning_proposal = proposals[winner_index - 1]
        state["adopted_norm"] = winning_proposal

        return {"tally": tally, "winner_index": winner_index, "winning_proposer": winning_proposer}

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


ACTION = VoteAction()
