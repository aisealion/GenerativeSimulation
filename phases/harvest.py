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
        # Ensure tracking structures exist
        runtime.setdefault('agent_trip_counts', {})
        runtime.setdefault('banned_agents', {})  # agent_id -> remaining banned trips
        runtime.setdefault('trip_records', [])  # ledger of trips
        runtime.setdefault('recent_catch_kg', [])  # list of total catch per round for last 30 rounds
        # Policy parameters based on norm.txt
        # Max per trip is 45% of current lake stock
        PER_TRIP_CAP_KG = 0.45 * stock_before
        # No rolling community cap; total round cap handled after all agents harvest

        for agent_id in agents:
            # Check ban status
            bans_remaining = runtime['banned_agents'].get(agent_id, 0)
            if bans_remaining > 0:
                # Agent is banned this trip
                runtime['banned_agents'][agent_id] = bans_remaining - 1
                harvested = 0.0
                excess = 0.0
                # Record banned trip
                runtime['trip_records'].append({
                    "agent_id": agent_id,
                    "round": round_number,
                    "harvested_kg": harvested,
                    "excess_kg": excess,
                    "banned": True,
                })
                # No deposit or penalty for banned agents
                results[agent_id] = {"effort": 0.0, "harvested_kg": harvested, "reasoning": "Banned for policy violation"}
                continue

            cap = effort_cap(agent_id, config, fluents, runtime)
            response = call_fisher_agent(
                agent_id, round_number, "harvest", **self.prompt_fields(state, agent_id)
            )
            effort = min(1.0, max(0.0, float(response["effort"])) )
            # Base harvest from effort before any caps
            base_harvest = catch_from_effort(effort, stock_before, config)

            # Apply effort cap if present
            if cap is not None:
                base_harvest = min(base_harvest, cap)

            # Enforce per‑trip quota cap (40% of lake stock)
            if base_harvest > PER_TRIP_CAP_KG:
                # Exceeds quota: forfeit entire catch to communal pool
                forfeited = base_harvest
                config["communal_pool_kg"] = config.get("communal_pool_kg", 0) + forfeited
                harvested = 0.0
                excess = 0.0
            else:
                # No quota violation; apply excess handling if over cap (should be zero here)
                excess = max(0.0, base_harvest - PER_TRIP_CAP_KG)
                if excess > 0:
                    # Contribute 10 % of excess to communal reserve
                    contribution = 0.10 * excess
                    config["community_reserve_kg"] = config.get("community_reserve_kg", 0) + contribution
                    # Apply ban for next two trips
                    runtime['banned_agents'][agent_id] = runtime['banned_agents'].get(agent_id, 0) + 2
                harvested = min(base_harvest, PER_TRIP_CAP_KG)

        # No community rolling cap; enforce round‑level lake protection later

            # Deposit 1 % of (possibly reduced) harvest into maintenance fund
            maintenance_deposit = 0.01 * harvested
            config["maintenance_fund_kg"] = config.get("maintenance_fund_kg", 0) + maintenance_deposit

            # Update tracking structures
            runtime['agent_trip_counts'][agent_id] = runtime['agent_trip_counts'].get(agent_id, 0) + 1
            runtime['recent_catch_kg'].append(harvested)
            if len(runtime['recent_catch_kg']) > 30:
                runtime['recent_catch_kg'].pop(0)

            # Record trip in ledger
            runtime['trip_records'].append({
                "agent_id": agent_id,
                "round": round_number,
                "harvested_kg": harvested,
                "excess_kg": excess,
                "banned": False,
            })

            results[agent_id] = {
                "effort": effort,
                "harvested_kg": harvested,
                "reasoning": response.get("reasoning", ""),
            }


        # After all agents have harvested, enforce round‑level lake protection per norm
        total_harvested_round = sum(r["harvested_kg"] for r in results.values())
        stock_after_harvest = stock_before - total_harvested_round
        if total_harvested_round > 0.70 * stock_before:
            # Replenish lake to pre‑harvest stock before regrowth (norm requires replenishment if >70% caught)
            stock_after_harvest = stock_before
        # Apply regrowth after harvest (or after replenishment)
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
