# Reads: state/config.json, state/fluents.json.
# Writes: state/runtime.json (proposals for the round).

from llm_agents import call_fisher_agent
from phases.base import Phase


class ProposePhase(Phase):
    name = "propose"

    def prompt_fields(self, state, agent_id):
        runtime = state["runtime"]
        agents = state["agents"]
        agent_ids = list(agents.keys())
        other_id = next(a for a in agent_ids if a != agent_id)
        last_harvest = next(r for r in reversed(runtime["rounds"]) if r["phase"] == "harvest")
        return {
            "your_catch_kg": last_harvest["agents"][agent_id]["harvested_kg"],
            "other_agent_name": agents[other_id]["name"],
            "other_catch_kg": last_harvest["agents"][other_id]["harvested_kg"],
            "stock_kg": runtime["stock_kg"],
        }

    def run(self, state):
        runtime = state["runtime"]
        agents = state["agents"]
        round_number = state["round_number"]
        agent_ids = list(agents.keys())

        proposals = {}
        for agent_id in agent_ids:
            response = call_fisher_agent(
                agent_id, round_number, "propose", **self.prompt_fields(state, agent_id)
            )
            proposals[agent_id] = {
                "policy": response["policy"],
                "operationalization": response["operationalization"],
                "reasoning": response.get("reasoning", ""),
            }

        round_record = {
            "round": round_number,
            "phase": "propose",
            "proposals": proposals,
        }

        runtime["round"] = round_number
        runtime["rounds"].append(round_record)
        return round_record

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


PHASE = ProposePhase()
