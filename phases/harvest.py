# Reads: state/config.json (effort caps, catchability, capacity), state/fluents.json (role holders).
# Writes: state/runtime.json (today's catch).

from mechanisms.effort import catch_from_effort, effort_cap
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
            "carrying_capacity_kg": config.get("carrying_capacity_kg", 0),
            "cap_line": cap_line,
        }

    def run(self, state):
        config = state["config"]
        fluents = state["fluents"]
        runtime = state["runtime"]
        agents = state["agents"]
        round_number = state["round_number"]

        stock_before = available_stock(runtime)
        results = {}
        for agent_id in agents:
            cap = effort_cap(agent_id, config, fluents, runtime)
            response = call_fisher_agent(
                agent_id, round_number, "harvest", **self.prompt_fields(state, agent_id)
            )
            effort = min(1.0, max(0.0, float(response["effort"])))
            harvested = catch_from_effort(effort, stock_before, config)
            if cap is not None:
                harvested = min(harvested, cap)
            results[agent_id] = {
                "effort": effort,
                "harvested_kg": harvested,
                "reasoning": response.get("reasoning", ""),
            }

        # Enforce community 5% reserve after all agents have harvested
        # Maximum total harvest allowed so that at least 5% of the pre‑harvest stock remains
        max_total_harvest = 0.95 * stock_before
        total_harvest = sum(r["harvested_kg"] for r in results.values())
        if total_harvest > max_total_harvest:
            # Reduce excess from the agent with the largest harvest (simple heuristic)
            excess = total_harvest - max_total_harvest
            # Find agent with max harvest
            max_aid = max(results, key=lambda a: results[a]["harvested_kg"])
            results[max_aid]["harvested_kg"] = max(0.0, results[max_aid]["harvested_kg"] - excess)

        # Weekly accounting (now renamed to rolling 7‑day tracking)
        # Update rolling history for each agent
        rolling = runtime.setdefault("rolling_7d", {})
        for aid, rec in results.items():
            hist = rolling.setdefault(aid, [])
            hist.append(rec["harvested_kg"])
            # Keep only the most recent 7 entries
            if len(hist) > 7:
                hist.pop(0)

        # Monthly reserve: 15% of total monthly harvest is set aside.
        month_index = (round_number - 1) // 30
        month_data = runtime.setdefault("monthly_harvest", {})
        month_key = f"month_{month_index}"
        month_record = month_data.setdefault(month_key, {"agents": {}, "total_harvested_kg": 0.0, "reserve_kg": 0.0})
        # Update agents' cumulative harvest for the month (excluding reserve)
        for aid, rec in results.items():
            month_record["agents"][aid] = month_record["agents"].get(aid, 0.0) + rec["harvested_kg"]
        month_total = sum(month_record["agents"].values())
        month_record["total_harvested_kg"] = month_total
        month_record["reserve_kg"] = 0.15 * month_total


        
        # No proportional rationing here — matches Gupta et al.'s CPRAgent.harvest(),
        # which subtracts each agent's independently-computed catch (all against the
        # same pre-harvest stock) directly, letting the stock go negative if
        # oversubscribed. The existing collapse check below (stock <= 0) is this
        # project's equivalent of their stop-the-simulation condition.
        stock_after_harvest = stock_before - sum(r["harvested_kg"] for r in results.values())
        stock_after_regrowth = apply_regrowth(stock_after_harvest, config)

        round_record = {
            "round": round_number,
            "phase": "harvest",
            "stock_kg_before": stock_before,
            "agents": {
                agent_id: {
                    "effort": results[agent_id]["effort"],
                    "harvested_kg": results[agent_id]["harvested_kg"],
                    "reasoning": results[agent_id]["reasoning"],
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
