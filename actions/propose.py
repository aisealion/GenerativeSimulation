# Reads: state/config.json, state/fluents.json.
# Writes: state/runtime.json (proposals for the round).

from engine.llm_agents import call_fisher_agent
from engine.phase_base import Phase
from engine.physics import alive_agent_ids


class ProposePhase(Phase):
    name = "propose"

    def prompt_fields(self, state, agent_id):
        runtime = state["runtime"]
        agents = state["agents"]
        agent_ids = alive_agent_ids(agents, runtime)
        last_harvest = next(r for r in reversed(runtime["rounds"]) if r["phase"] == "harvest")

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

    def run(self, state):
        runtime = state["runtime"]
        agents = state["agents"]
        round_number = state["round_number"]
        agent_ids = alive_agent_ids(agents, runtime)

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
