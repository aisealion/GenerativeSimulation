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
        # Prompt now includes weekly quota info
        stock_before = available_stock(runtime)
        quota_kg = max(stock_before * 0.10, 5.0)
        cap_line = f" Your weekly quota is {quota_kg:.0f}kg (max 2 trips per week)."
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

        # Initialize weekly trip tracking if absent
        if "weekly_trips" not in runtime:
            runtime["weekly_trips"] = {}
        stock_before = available_stock(runtime)
        results = {}
        # Determine the quota for this round based on current stock (10% or 5 kg minimum)
        quota_kg = max(stock_before * 0.10, 5.0)
        current_week = round_number // 7  # integer division defines a week of 7 rounds
        for agent_id in agents:
            # Retrieve or initialize this fisher's weekly record
            week_record = runtime["weekly_trips"].get(agent_id, {"week": current_week, "count": 0})
            # Reset count if we have moved to a new week
            if week_record["week"] != current_week:
                week_record = {"week": current_week, "count": 0}
            # Enforce max two trips per week
            if week_record["count"] >= 2:
                cap = 0.0
            else:
                cap = quota_kg
            response = call_fisher_agent(
                agent_id, round_number, "harvest", **self.prompt_fields(state, agent_id)
            )
            effort = min(1.0, max(0.0, float(response["effort"])) )
            harvested = catch_from_effort(effort, stock_before, config)
            # Apply per‑trip cap (max 25 kg) and daily community limit (225 kg)
            # First enforce the per‑trip limit
            harvested = min(harvested, 25.0, cap)
            # Then enforce the remaining daily community allowance
            remaining_daily = max(0.0, 225.0 - sum(r["harvested_kg"] for r in results.values()))
            harvested = min(harvested, remaining_daily)
            results[agent_id] = {
                "effort": effort,
                "harvested_kg": harvested,
                "reasoning": response.get("reasoning", ""),
            }
            # Update weekly trip count (only count trips where effort > 0)
            if effort > 0:
                week_record["count"] += 1
            runtime["weekly_trips"][agent_id] = week_record

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
