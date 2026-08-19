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
        # Determine the current month index and ensure monthly quota is initialized
        month_index = state["round_number"] // 30
        if runtime.get("monthly_month") != month_index:
            # Reset monthly tracking at the start of a new month
            stock_start = available_stock(runtime)
            runtime["monthly_month"] = month_index
            runtime["monthly_stock_start"] = stock_start
            runtime["monthly_quota_total"] = min(stock_start * 0.12, 90.0)
            runtime["monthly_used"] = 0.0
            runtime["monthly_fisher"] = {}
        # Per-fisher monthly quota (5% of stock start, capped at 8 kg)
        per_fisher_quota = min(runtime["monthly_stock_start"] * 0.05, 8.0)
        cap_line = f" Your monthly quota is {per_fisher_quota:.0f}kg per trip (max 8 kg)."
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
        # Determine per-fisher monthly quota (5% of start‑of‑month stock, capped at 8 kg)
        per_fisher_quota = min(runtime["monthly_stock_start"] * 0.05, 8.0)
        current_month = state["round_number"] // 30
        for agent_id in agents:
            # Retrieve or initialize this fisher's monthly usage record
            fisher_record = runtime["monthly_fisher"].get(agent_id, {"used": 0.0})
            # If this fisher has already used their monthly quota, cap to 0
            if fisher_record["used"] >= per_fisher_quota:
                cap = 0.0
            else:
                cap = per_fisher_quota - fisher_record["used"]
            response = call_fisher_agent(
                agent_id, round_number, "harvest", **self.prompt_fields(state, agent_id)
            )
            effort = min(1.0, max(0.0, float(response["effort"])) )
            harvested = catch_from_effort(effort, stock_before, config)
            # Apply per‑trip cap (max 8 kg) and per‑fisher monthly remaining quota
            harvested = min(harvested, 8.0, cap)
            # Enforce community monthly cap (12% of start‑of‑month stock, capped at 90 kg)
            remaining_monthly = max(0.0, runtime["monthly_quota_total"] - runtime["monthly_used"])
            harvested = min(harvested, remaining_monthly)
            results[agent_id] = {
                "effort": effort,
                "harvested_kg": harvested,
                "reasoning": response.get("reasoning", ""),
            }
            # Update monthly usage records (only count trips where effort > 0)
            if effort > 0:
                fisher_record["used"] += harvested
                runtime["monthly_used"] += harvested
                runtime["monthly_fisher"][agent_id] = fisher_record
            # No weekly trip count needed under new policy
        
        # No proportional rationing here — matches Gupta et al.'s CPRAgent.harvest(),
        # which subtracts each agent's independently-computed catch (all against the
        # same pre-harvest stock) directly, letting the stock go negative if
        # oversubscribed. The existing collapse check below (stock <= 0) is this
        # project's equivalent of their stop-the-simulation condition.
        stock_after_harvest = stock_before - sum(r["harvested_kg"] for r in results.values())
        stock_after_regrowth = apply_regrowth(stock_after_harvest, config)
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
