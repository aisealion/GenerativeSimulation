# Reads: state/config.json (effort caps, catchability, capacity), state/fluents.json (role holders).
# Writes: state/runtime.json (today's catch).

from mechanisms.effort import catch_from_effort
import datetime
from mechanisms.stock_check import available_stock, apply_regrowth
from llm_agents import call_fisher_agent
from phases.base import Phase


class HarvestPhase(Phase):
    name = "harvest"

    def prompt_fields(self, state, agent_id):
        # Provide stock info for the fisher persona (no per‑trip cap).
        config = state["config"]
        runtime = state["runtime"]
        stock = available_stock(runtime)
        return {
            "stock_kg": stock,
            "carrying_capacity_kg": config.get("carrying_capacity_kg", 0),
        }

    def run(self, state):
        config = state["config"]
        fluents = state["fluents"]
        runtime = state["runtime"]
        agents = state["agents"]
        round_number = state["round_number"]

        stock_before = available_stock(runtime)
        reserve_before = config.get("community_reserve_kg", 0)
        results = {}
        # Initialize tracking structures if not present
        runtime.setdefault('agent_trip_counts', {})
        runtime.setdefault('trip_records', [])  # ledger of trips
        runtime.setdefault('recent_catch_kg', [])  # keep last 30 rounds total catch
        runtime.setdefault('last_trip_round', {})
        runtime.setdefault('banned_agents', {})

        # Norm check: prohibit fishing if lake or reserve below thresholds
        if stock_before < 95 or reserve_before < 95:
            # No fishing this round for any agent
            for agent_id in agents:
                results[agent_id] = {"effort": 0.0, "harvested_kg": 0.0, "reasoning": "Fishing prohibited due to low stock or reserve"}
                runtime['trip_records'].append({
                    "agent_id": agent_id,
                    "round": round_number,
                    "harvested_kg": 0.0,
                    "excess_kg": 0.0,
                    "banned": True,
                })
            total_harvested_round = 0.0
            stock_after_harvest = stock_before
        else:
            for agent_id in agents:
                # Rest requirement: if fished previous round, treat as ban
                if runtime.get('last_trip_round', {}).get(agent_id) == round_number - 1:
                    # Agent must rest; no harvest this round
                    runtime['banned_agents'][agent_id] = runtime['banned_agents'].get(agent_id, 0) + 1
                    harvested = 0.0
                    runtime['trip_records'].append({
                        "agent_id": agent_id,
                        "round": round_number,
                        "harvested_kg": harvested,
                        "excess_kg": 0.0,
                        "banned": True,
                    })
                    results[agent_id] = {"effort": 0.0, "harvested_kg": harvested, "reasoning": "Rest requirement violation"}
                    continue
                bans_remaining = runtime['banned_agents'].get(agent_id, 0)
                if bans_remaining > 0:
                    # Agent is banned this trip
                    runtime['banned_agents'][agent_id] = bans_remaining - 1
                    harvested = 0.0
                    runtime['trip_records'].append({
                        "agent_id": agent_id,
                        "round": round_number,
                        "harvested_kg": harvested,
                        "excess_kg": 0.0,
                        "banned": True,
                    })
                    results[agent_id] = {"effort": 0.0, "harvested_kg": harvested, "reasoning": "Banned for policy violation"}
                    continue

                response = call_fisher_agent(
                    agent_id, round_number, "harvest", **self.prompt_fields(state, agent_id)
                )
                effort = min(1.0, max(0.0, float(response["effort"])) )
                base_harvest = catch_from_effort(effort, stock_before, config)
                # Apply per‑trip cap of 0.7 kg as defined in norm.txt
                per_trip_cap = 0.7
                harvested = min(base_harvest, per_trip_cap, stock_before)
                # Deposit 60 % of caught fish into communal reserve
                deposit = 0.6 * harvested
                config["community_reserve_kg"] = config.get("community_reserve_kg", 0) + deposit
                # Record trip
                runtime['trip_records'].append({
                    "agent_id": agent_id,
                    "round": round_number,
                    "harvested_kg": harvested,
                    "excess_kg": 0.0,
                    "banned": False,
                })
                runtime['last_trip_round'][agent_id] = round_number
                runtime['agent_trip_counts'][agent_id] = runtime['agent_trip_counts'].get(agent_id, 0) + 1
                results[agent_id] = {"effort": effort, "harvested_kg": harvested, "reasoning": response.get("reasoning", "")}

            total_harvested_round = sum(r["harvested_kg"] for r in results.values())
            # Reduce lake stock by total harvested (cannot go negative)
            stock_after_harvest = max(stock_before - total_harvested_round, 0)

        # Apply regrowth after harvest (or after any replenishment)
        stock_after_regrowth = apply_regrowth(stock_after_harvest, config)

        round_record = {
            "round": round_number,
            "phase": "harvest",
            "stock_kg_before": stock_before,
            "reserve_kg_before": reserve_before,
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
            "reserve_kg_after": config.get("community_reserve_kg", 0),
        }

        runtime["round"] = round_number
        runtime["stock_kg"] = stock_after_regrowth
        runtime["rounds"].append(round_record)
        return round_record


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
