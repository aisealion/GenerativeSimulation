# Reads: state/config.json (effort caps, catchability, capacity), state/fluents.json (role holders).
# Writes: state/runtime.json (today's catch).

from mechanisms.effort import catch_from_effort, effort_cap
from mechanisms.penalty import apply_penalty
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
        runtime.setdefault('agent_trip_counts', {})
        runtime.setdefault('trip_records', [])  # ledger of trips
        runtime.setdefault('recent_catch_kg', [])  # list of total catch per round for last 30 rounds
        # Policy parameters based on norm.txt
        # Per‑fisher cap: 2% of current lake stock per month (treated as per‑trip cap here)
        PER_TRIP_CAP_KG = 0.02 * stock_before
        # Community monthly cap: 5% of stock (enforced cumulatively within the round)
        COMMUNITY_CAP_KG = 0.05 * stock_before
        # Enforce community monthly cap after agents harvest

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

            # Enforce per‑trip quota cap (100% of lake stock) per norm
            excess = max(0.0, base_harvest - PER_TRIP_CAP_KG)
            harvested = min(base_harvest, PER_TRIP_CAP_KG)



            # Update tracking structures
            runtime['agent_trip_counts'][agent_id] = runtime['agent_trip_counts'].get(agent_id, 0) + 1
            runtime['recent_catch_kg'].append(harvested)
            if len(runtime['recent_catch_kg']) > 30:
                runtime['recent_catch_kg'].pop(0)

            excess = 0.0  # already accounted; keep variable for ledger

            # Deposit 12% of catch into communal restocking fund
            deposit_amount = 0.12 * harvested
            runtime["community_reserve_kg"] = runtime.get("community_reserve_kg", 0) + deposit_amount
            # Reduce harvested amount by deposit (already accounted in harvested)
            # Note: deposit taken from harvested, not extra
            harvested -= deposit_amount
            penalty_factors = runtime.get('penalty_factors', {})
            factor = penalty_factors.get(agent_id, 1.0)
            harvested = harvested * factor
            # Reset penalty for next round after applied
            if agent_id in penalty_factors:
                del runtime['penalty_factors'][agent_id]
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


        # Apply community cap if total exceeds COMMUNITY_CAP_KG
        total_harvested_round = sum(r["harvested_kg"] for r in results.values())
        if total_harvested_round > COMMUNITY_CAP_KG:
            # Scale down proportionally to meet community cap
            scale = COMMUNITY_CAP_KG / total_harvested_round
            for rec in results.values():
                rec["harvested_kg"] *= scale
            total_harvested_round = COMMUNITY_CAP_KG
        stock_after_harvest = stock_before - total_harvested_round
        if total_harvested_round > 0.90 * stock_before:
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
