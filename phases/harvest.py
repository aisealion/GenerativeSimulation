# Reads: state/config.json (effort caps, catchability, capacity), state/fluents.json (role holders).
# Writes: state/runtime.json (today's catch).

from mechanisms.effort import catch_from_effort
from mechanisms.stock_check import available_stock, apply_regrowth
from llm_agents import call_fisher_agent
from phases.base import Phase


class HarvestPhase(Phase):
    name = "harvest"

    def prompt_fields(self, state, agent_id):
        config = state["config"]
        fluents = state["fluents"]
        runtime = state["runtime"]
        # 10% of current stock is the cap per the norm
        stock = available_stock(runtime)
        cap = 0.10 * stock
        cap_line = f" You may harvest up to 10% of the lake ({cap:.0f}kg) this trip."
        return {
            "stock_kg": stock,
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

        # Ensure communal pot, excess pending, and penalties structures exist
        runtime.setdefault("communal_pot_kg", 0.0)
        runtime.setdefault("excess_pending", {})
        runtime.setdefault("penalties", {})

        # Mandatory rest day every 7 rounds (Sunday)
        if round_number % 7 == 0:
            # No fishing today; all agents harvest zero
            results = {
                agent_id: {
                    "effort": 0.0,
                    "harvested_kg": 0.0,
                    "reasoning": "Rest day (no fishing)",
                }
                for agent_id in agents
            }
            stock_after_harvest = stock_before
            stock_after_regrowth = apply_regrowth(stock_after_harvest, config)
            round_record = {
                "round": round_number,
                "phase": "harvest",
                "stock_kg_before": stock_before,
                "agents": results,
                "stock_kg_after_harvest": stock_after_harvest,
                "stock_kg_after_regrowth": stock_after_regrowth,
            }
            runtime["round"] = round_number
            runtime["stock_kg"] = stock_after_regrowth
            runtime["rounds"].append(round_record)
            return round_record

        # Enforce per‑fisher limit of 15 kg (norm) and apply any pending penalties
        results = {}
        total_harvested = 0.0
        for agent_id in agents:
            response = call_fisher_agent(
                agent_id, round_number, "harvest", **self.prompt_fields(state, agent_id)
            )
            effort = min(1.0, max(0.0, float(response["effort"])) )
            harvested = catch_from_effort(effort, stock_before, config)
            # Apply per‑trip maximum
            if harvested > 15:
                excess = harvested - 15
                runtime["communal_pot_kg"] = runtime.get("communal_pot_kg", 0.0) + excess
                runtime["excess_pending"][agent_id] = excess
                harvested = 15.0
            # Apply any penalty from previous non‑deposit
            penalty = runtime["penalties"].pop(agent_id, 0)
            if penalty:
                runtime["communal_pot_kg"] = runtime.get("communal_pot_kg", 0.0) + penalty
                harvested = max(0.0, harvested - penalty)
            results[agent_id] = {
                "effort": effort,
                "harvested_kg": harvested,
                "reasoning": response.get("reasoning", ""),
            }
            total_harvested += harvested



        
        # Apply daily total cap (70% of stock, leaving at least 20 kg)
        daily_cap = min(0.70 * stock_before, max(stock_before - 20, 0))
        if total_harvested > daily_cap:
            excess_total = total_harvested - daily_cap
            # proportionally reduce each fisher's harvest and record penalty
            for agent_id, rec in results.items():
                original = rec["harvested_kg"]
                if original <= 0:
                    continue
                # proportion of this fisher's contribution to total
                proportion = original / total_harvested
                reduction = proportion * excess_total
                new_harvest = max(0.0, original - reduction)
                penalty_amount = original - new_harvest
                rec["harvested_kg"] = new_harvest
                # add penalty to communal pot and track per‑agent penalty for future rounds
                runtime["communal_pot_kg"] = runtime.get("communal_pot_kg", 0.0) + penalty_amount
                runtime.setdefault("penalties", {}).setdefault(agent_id, 0)
                runtime["penalties"][agent_id] = runtime["penalties"].get(agent_id, 0) + penalty_amount
            total_harvested = daily_cap
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

        # Distribute communal pot when lake stock falls below 70 kg
        if stock_after_regrowth < 70 and runtime.get("communal_pot_kg", 0) > 0:
            num_agents = len(agents)
            share = runtime["communal_pot_kg"] / num_agents if num_agents else 0
            # Record distribution event
            runtime.setdefault("pot_distributions", []).append({
                "round": round_number,
                "total_kg": runtime["communal_pot_kg"],
                "share_per_agent_kg": share,
            })
            # Reset pot after distribution
            runtime["communal_pot_kg"] = 0.0
        
        runtime["round"] = round_number
        runtime["stock_kg"] = stock_after_regrowth
        runtime["rounds"].append(round_record)
        return round_record


PHASE = HarvestPhase()
