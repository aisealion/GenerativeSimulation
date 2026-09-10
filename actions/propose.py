# Reads: state/config.json, state/fluents.json.
# Writes: state/runtime.json (proposals for the round).

from engine.llm_agents import call_fisher_agent
from engine.action_base import SimpleAgentAction


class ProposeAction(SimpleAgentAction):
    name = "propose"

    def setup(self, state):
        """The most recent harvest round record — hoisted to once per round
        instead of being recomputed on every agent's own prompt_fields()
        call, since it only reads history strictly before this round, never
        mutated by this round's own proposal loop."""
        return next(r for r in reversed(state["runtime"]["rounds"]) if r["action"] == "harvest")

    def build_fields(self, state, setup_ctx, agent_id):
        last_harvest = setup_ctx
        runtime, agents = state["runtime"], state["agents"]
        agent_ids = self.participants(state, setup_ctx)

        others_summary = "\n".join(
            f"- {agents[other_id]['name']} brought in {last_harvest['agents'][other_id]['harvested_kg']:.0f}kg."
            for other_id in agent_ids
            if other_id != agent_id
        )

        return {
            "your_catch_kg": last_harvest["agents"][agent_id]["harvested_kg"],
            "others_summary": others_summary,
            "stock_kg": runtime["stock_kg"],
        }

    def call_agent(self, agent_id, round_number, fields):
        return call_fisher_agent(agent_id, round_number, self.name, **fields)

    def record_result(self, state, setup_ctx, agent_id, response):
        return {
            "policy": response["policy"],
            "operationalization": response["operationalization"],
            "reasoning": response.get("reasoning", ""),
        }

    def per_agent_key(self):
        return "proposals"

    def memory_writes(self, state, round_record):
        return [
            {
                "event_type": "proposal_made",
                "text": f"you proposed: {proposal['policy']}",
                "agent_id": agent_id,
                "group_id": agent_id,
            }
            for agent_id, proposal in round_record["proposals"].items()
        ]


ACTION = ProposeAction()
