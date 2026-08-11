# Reads: state/config.json, state/fluents.json.
# Writes: state/runtime.json (proposals for the round).

from llm_agents import call_fisher_agent


def run(state):
    runtime = state["runtime"]
    agents = state["agents"]
    round_number = state["round_number"]
    agent_ids = list(agents.keys())

    last_harvest = next(r for r in reversed(runtime["rounds"]) if r["phase"] == "harvest")

    proposals = {}
    for agent_id in agent_ids:
        other_id = next(a for a in agent_ids if a != agent_id)
        response = call_fisher_agent(
            agent_id,
            round_number,
            "propose",
            your_catch_kg=last_harvest["agents"][agent_id]["harvested_kg"],
            other_agent_name=agents[other_id]["name"],
            other_catch_kg=last_harvest["agents"][other_id]["harvested_kg"],
            stock_kg=runtime["stock_kg"],
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
