# Reads: state/config.json (effort caps), state/fluents.json (role holders).
# Writes: state/runtime.json (today's catch).

from mechanisms.effort import effort_cap
from mechanisms.stock_check import available_stock, apply_regrowth
from llm_agents import call_fisher_agent
from phases.base import Phase


class HarvestPhase(Phase):
    name = "harvest"

    def prompt_fields(self, state, agent_id):
        config = state["config"]
        fluents = state["fluents"]
        runtime = state["runtime"]
        cap = effort_cap(agent_id, config, fluents, runtime)
        cap_line = (
            f" You currently have an agreed limit of {cap:.0f}kg for this trip."
            if cap is not None
            else ""
        )
        return {
            "stock_kg": available_stock(runtime),
            "regrowth_kg": config.get("regrowth_kg_per_round", 0),
            "cap_line": cap_line,
        }

    def run(self, state):
        config = state["config"]
        fluents = state["fluents"]
        runtime = state["runtime"]
        agents = state["agents"]
        round_number = state["round_number"]

        stock_before = available_stock(runtime)
        requests = {}
        for agent_id in agents:
            cap = effort_cap(agent_id, config, fluents, runtime)
            response = call_fisher_agent(
                agent_id, round_number, "harvest", **self.prompt_fields(state, agent_id)
            )
            requested = max(0.0, float(response["harvest_kg"]))
            if cap is not None:
                requested = min(requested, cap)
            requests[agent_id] = {"requested_kg": requested, "reasoning": response.get("reasoning", "")}

        total_requested = sum(r["requested_kg"] for r in requests.values())
        if total_requested <= stock_before:
            actual = {agent_id: r["requested_kg"] for agent_id, r in requests.items()}
        else:
            ratio = stock_before / total_requested
            actual = {agent_id: r["requested_kg"] * ratio for agent_id, r in requests.items()}

        stock_after_harvest = stock_before - sum(actual.values())
        stock_after_regrowth = apply_regrowth(stock_after_harvest, config)

        round_record = {
            "round": round_number,
            "phase": "harvest",
            "stock_kg_before": stock_before,
            "agents": {
                agent_id: {
                    "requested_kg": requests[agent_id]["requested_kg"],
                    "harvested_kg": actual[agent_id],
                    "reasoning": requests[agent_id]["reasoning"],
                }
                for agent_id in agents
            },
            "stock_kg_after_harvest": stock_after_harvest,
            "stock_kg_after_regrowth": stock_after_regrowth,
        }

        runtime["round"] = round_number
        runtime["stock_kg"] = stock_after_regrowth
        runtime["rounds"].append(round_record)
        return round_record


PHASE = HarvestPhase()
