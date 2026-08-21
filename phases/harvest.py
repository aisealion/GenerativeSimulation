# Reads: state/config.json (effort caps, catchability, capacity), state/fluents.json (role holders).
# Writes: state/runtime.json (today's catch).

from mechanisms.effort import catch_from_effort
import datetime
from mechanisms.penalty import apply_penalty
from llm_agents import call_fisher_agent
from phases.base import Phase


class HarvestPhase(Phase):
    name = "harvest"

    def prompt_fields(self, state, agent_id):
        # Provide stock info and per‑trip cap message for the fisher persona.
        config = state["config"]
        fluents = state["fluents"]
        runtime = state["runtime"]
        # Compute per‑trip cap (2 % of stock or 2 kg, whichever is lower)
        stock = available_stock(runtime)
        per_trip_cap = min(0.02 * stock, 2.0)
        cap_line = f" You currently have a per‑trip limit of {per_trip_cap:.1f}kg (2 % of stock or 2 kg)."
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
        results = {}
        # Ensure tracking structures exist
        runtime.setdefault('agent_trip_counts', {})
        runtime.setdefault('agent_trip_counts', {})
        runtime.setdefault('trip_records', [])  # ledger of trips
        runtime.setdefault('recent_catch_kg', [])  # list of total catch per round for last 30 rounds
        # Track last trip round for each agent to enforce 48‑hour rest (skip if they fished previous round)
        runtime.setdefault('last_trip_round', {})
        # New norm: per‑trip cap is min(2% of stock, 2kg) – already calculated as PER_TRIP_CAP_KG
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

            # Compute per‑trip cap (2 % of current stock or 2 kg, whichever is lower)
            per_trip_cap = min(0.02 * stock_before, 2.0)
            response = call_fisher_agent(
                agent_id, round_number, "harvest", **self.prompt_fields(state, agent_id)
            )
            effort = min(1.0, max(0.0, float(response["effort"])) )
            # Base harvest from effort before caps
            base_harvest = catch_from_effort(effort, stock_before, config)

            # Apply per‑trip cap
            if base_harvest > per_trip_cap:
                excess_trip = base_harvest - per_trip_cap
                harvested = per_trip_cap
            else:
                excess_trip = 0.0
                harvested = base_harvest

            # Apply 25 % restocking contribution from harvested amount
            donation = 0.25 * harvested
            kept = harvested - donation

            # Track monthly catch and enforce monthly cap (3 kg total kept per fisher per month)
            now_month = datetime.datetime.now().month
            # Initialize month tracking structures if needed
            runtime.setdefault('monthly_catch', {})
            runtime.setdefault('monthly_month', now_month)
            if runtime['monthly_month'] != now_month:
                # New month: reset monthly catches and warnings
                runtime['monthly_catch'] = {}
                runtime['monthly_month'] = now_month
                runtime.setdefault('warnings', {})
                runtime['warnings'] = {}
                runtime.setdefault('banned_months', {})
                runtime['banned_months'] = {}
            month_total = runtime['monthly_catch'].get(agent_id, 0.0) + kept
            if month_total > 3.0:
                excess_month = month_total - 3.0
                # Apply penalty: 10 % of excess goes to fund, issue warning
                penalty_fund = 0.10 * excess_month
                runtime.setdefault('restocking_fund_kg', 0.0)
                runtime['restocking_fund_kg'] += penalty_fund
                # Increment warnings
                runtime.setdefault('warnings', {})
                runtime['warnings'][agent_id] = runtime['warnings'].get(agent_id, 0) + 1
                if runtime['warnings'][agent_id] >= 2:
                    # Ban for next month
                    runtime.setdefault('banned_months', {})
                    runtime['banned_months'][agent_id] = now_month + 1
                # Cap kept to 3 kg
                kept = 3.0
                month_total = 3.0
            else:
                excess_month = 0.0
                # No penalty for this trip
                runtime.setdefault('restocking_fund_kg', 0.0)
                runtime['restocking_fund_kg'] += donation

            # Update monthly catch record
            runtime['monthly_catch'][agent_id] = month_total

            # Update last trip round after successful harvest
            runtime['last_trip_round'][agent_id] = round_number
            runtime['agent_trip_counts'][agent_id] = runtime['agent_trip_counts'].get(agent_id, 0) + 1
            runtime['recent_catch_kg'].append(kept)
            if len(runtime['recent_catch_kg']) > 30:
                runtime['recent_catch_kg'].pop(0)

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
        # Community cap still applies to total harvested after redistribution
        COMMUNITY_CAP_KG = 0.03 * stock_before
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
