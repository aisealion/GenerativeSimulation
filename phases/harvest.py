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
        results = {}
        # Ensure tracking structures exist
        runtime.setdefault('agent_trip_counts', {})
        runtime.setdefault('agent_trip_counts', {})
        runtime.setdefault('trip_records', [])  # ledger of trips
        runtime.setdefault('recent_catch_kg', [])  # list of total catch per round for last 30 rounds
        # Track last trip round for each agent to enforce 48‑hour rest (skip if they fished previous round)
        runtime.setdefault('last_trip_round', {})
                # New norm: no per‑trip cap; catch up to 100% of current lake weight per fisher
                # (per‑trip cap removed – harvest directly from effort)
        # No community cap enforced; reserve must stay >= 90 kg (handled elsewhere)

        for agent_id in agents:
            # Check rest requirement: if fished previous round, treat as ban for this round
            if runtime.get('last_trip_round', {}).get(agent_id) == round_number - 1:
                # Agent must rest; no harvest this round
                runtime['banned_agents'][agent_id] = runtime['banned_agents'].get(agent_id, 0) + 1  # add a ban round
                harvested = 0.0
                excess = 0.0
                runtime['trip_records'].append({
                    "agent_id": agent_id,
                    "round": round_number,
                    "harvested_kg": harvested,
                    "excess_kg": excess,
                    "banned": True,
                })
                results[agent_id] = {"effort": 0.0, "harvested_kg": harvested, "reasoning": "Rest requirement violation"}
                continue
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

            # Compute per‑trip cap (removed per new norm)
            response = call_fisher_agent(
                agent_id, round_number, "harvest", **self.prompt_fields(state, agent_id)
            )
            # effort is fisher's chosen intensity; no per‑trip cap applied
            effort = min(1.0, max(0.0, float(response["effort"])) )
            # Base harvest from effort before caps; enforce max 100% of current stock
            base_harvest = catch_from_effort(effort, stock_before, config)
            # If base_harvest exceeds stock, limit to stock (100% catch) and note violation
            if base_harvest > stock_before:
                harvested = stock_before
                # No further penalty logic implemented; future catch forfeiture not needed as each agent fishes once per round
            else:
                harvested = base_harvest
            excess_trip = 0.0



            # Update last trip round after successful harvest
            runtime['last_trip_round'][agent_id] = round_number
            runtime['agent_trip_counts'][agent_id] = runtime['agent_trip_counts'].get(agent_id, 0) + 1
            results[agent_id] = {"effort": effort, "harvested_kg": harvested, "reasoning": response.get("reasoning", "")}

            excess = excess_trip + excess_month



            # Update last trip round after successful harvest
            runtime['last_trip_round'][agent_id] = round_number
            runtime['agent_trip_counts'][agent_id] = runtime['agent_trip_counts'].get(agent_id, 0) + 1
            runtime['recent_catch_kg'].append(harvested)
            if len(runtime['recent_catch_kg']) > 30:
                runtime['recent_catch_kg'].pop(0)

            excess = 0.0  # already accounted; keep variable for ledger

        # Donation and penalty have been applied per‑agent inside the loop above.
        # At this point, `results` already contains each fisher's `kept` amount under the key `harvested_kg`.
        # No further post‑processing is needed here.


        # After processing all agents, handle pool redistribution to zero‑catchers
        total_donation = sum([rec.get('donation', 0.0) for rec in results.values()])
        zero_catch_ids = [aid for aid, rec in results.items() if rec['harvested_kg'] == 0]
        if zero_catch_ids:
            share = total_donation / len(zero_catch_ids)
            for aid in zero_catch_ids:
                results[aid]['harvested_kg'] += share
        # New norm: no community cap; lake replenishes if total catch exceeds 250% of current stock
        total_harvested_round = sum(r["harvested_kg"] for r in results.values())
        if total_harvested_round > 2.5 * stock_before:
            # Replenish lake to pre‑harvest stock
            stock_after_harvest = stock_before
        else:
            # Reduce stock by total harvested, but not below zero
            stock_after_harvest = max(stock_before - total_harvested_round, 0)
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
