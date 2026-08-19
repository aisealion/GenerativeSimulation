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

        # Enforce community monthly total catch limit (norm: 12 % of current biomass, capped at 90 kg).
        # Determine the current month index (30 rounds per month approximation).
        month_index = (round_number - 1) // 30
        # Retrieve prior month cumulative harvest, if any.
        month_data = runtime.setdefault("monthly_harvest", {})
        month_key = f"month_{month_index}"
        prior = month_data.get(month_key, {"agents": {}, "total_harvested_kg": 0.0})
        prior_total = prior.get("total_harvested_kg", 0.0)
        # Compute monthly cap based on stock before this round.
        monthly_cap = min(0.12 * stock_before, 90.0)
        # Remaining allowance for this month.
        remaining = monthly_cap - prior_total
        if remaining <= 0:
            # No allowance left: set all catches this round to zero.
            for aid in results:
                results[aid]["harvested_kg"] = 0.0
        else:
            round_total = sum(r["harvested_kg"] for r in results.values())
            if round_total > remaining:
                # Scale down this round's harvest proportionally to fit remaining quota.
                scale = remaining / round_total
                for aid in results:
                    results[aid]["harvested_kg"] *= scale
        # Update month cumulative data.
        month_record = {
            aid: prior["agents"].get(aid, 0.0) + results[aid]["harvested_kg"] for aid in agents
        }
        month_data[month_key] = {
            "agents": month_record,
            "total_harvested_kg": prior_total + sum(r["harvested_kg"] for r in results.values()),
        }
        
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
