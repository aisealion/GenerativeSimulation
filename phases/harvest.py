# Reads: state/config.json (effort caps, catchability, capacity), state/fluents.json (role holders).
# Writes: state/runtime.json (today's catch).

from mechanisms.effort import catch_from_effort
import datetime
from mechanisms.stock_check import available_stock
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
        # Reserve is no longer used under the new norm; keep placeholder for compatibility
        reserve_before = 0
        results = {}
        # Tracking of reporting compliance – each fisher must report their catch each round.
        # We'll store a flag in runtime['reported_this_round'] for each agent.
        runtime.setdefault('reported_this_round', {})
        runtime.setdefault('agent_trip_counts', {})
        runtime.setdefault('trip_records', [])  # ledger of trips
        runtime.setdefault('recent_catch_kg', [])  # keep last 30 rounds total catch
        runtime.setdefault('last_trip_round', {})
        runtime.setdefault('banned_agents', {})

        # Removed early stock‑threshold ban – fishers may fish regardless of lake level
        
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
                    runtime['reported_this_round'][agent_id] = True
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
                    runtime['reported_this_round'][agent_id] = True
                    continue

                # Check for zero‑catch penalty from previous non‑report
                if agent_id in runtime.get('zero_next_round', {}):
                    # Apply zero catch for this round
                    harvested = 0.0
                    runtime['trip_records'].append({
                        "agent_id": agent_id,
                        "round": round_number,
                        "harvested_kg": harvested,
                        "excess_kg": 0.0,
                        "banned": False,
                    })
                    runtime['reported_this_round'][agent_id] = True
                    runtime['last_trip_round'][agent_id] = round_number
                    runtime['agent_trip_counts'][agent_id] = runtime['agent_trip_counts'].get(agent_id, 0) + 1
                    results[agent_id] = {"effort": 0.0, "harvested_kg": harvested, "reasoning": "Zero catch penalty for prior non‑report"}
                    # Remove the flag so it doesn't persist beyond this round
                    runtime['zero_next_round'].pop(agent_id, None)
                    continue
                effort = min(1.0, max(0.0, float(response["effort"])) )
                base_harvest = catch_from_effort(effort, stock_before, config)
        # Harvest phase now allows fishing regardless of stock level, as each fisher keeps all catch.
        # No communal reserve or contribution logic; excess_kg stays zero.
        
                runtime['trip_records'].append({
                    "agent_id": agent_id,
                    "round": round_number,
                    "harvested_kg": harvested,
                    "excess_kg": 0.0,
                    "banned": False,
                })
                runtime['reported_this_round'][agent_id] = True
                runtime['last_trip_round'][agent_id] = round_number
                runtime['agent_trip_counts'][agent_id] = runtime['agent_trip_counts'].get(agent_id, 0) + 1
                results[agent_id] = {"effort": effort, "harvested_kg": harvested, "reasoning": response.get("reasoning", "")}

        # Apply reporting compliance penalties
        runtime.setdefault('non_report_counts', {})
        runtime.setdefault('zero_next_round', {})
        for agent_id in agents:
            if not runtime['reported_this_round'].get(agent_id, False):
                # Increment non‑report count
                cnt = runtime['non_report_counts'].get(agent_id, 0) + 1
                runtime['non_report_counts'][agent_id] = cnt
                if cnt == 1:
                    # First offense: next round catch treated as zero
                    runtime['zero_next_round'][agent_id] = True
                else:
                    # Repeated offense: impose a ban (add to banned_agents)
                    runtime['banned_agents'][agent_id] = runtime['banned_agents'].get(agent_id, 0) + 1
            else:
                # Reset counts on compliance
                runtime['non_report_counts'][agent_id] = 0
                runtime['zero_next_round'].pop(agent_id, None)
        # Reset reporting flags for next round
        runtime['reported_this_round'] = {}
        # Enforce zero‑catch penalty for agents flagged from previous round
        for agent_id in list(runtime['zero_next_round'].keys()):
            # If still flagged (i.e., penalty not yet applied), set a temporary entry
            # We'll handle it in the per‑agent loop below by checking this dict
            pass
        # Determine total harvested this round
        total_harvested_round = sum(r["harvested_kg"] for r in results.values())
        # Community 30‑day harvest limit (40 kg)
        recent_community_harvest = sum(rec["harvested_kg"] for rec in runtime['trip_records'] if rec["round"] >= round_number - 29)
        if recent_community_harvest > 40.0:
            # Exceeds cap: cancel this round's harvests
            for aid in results:
                results[aid]["harvested_kg"] = 0.0
                results[aid]["reasoning"] = "Community harvest cap exceeded; no harvest allowed"
            total_harvested_round = 0.0
        # Compute stock after harvest (cannot go negative)
        stock_after_harvest = max(stock_before - total_harvested_round, 0)

        # Apply replenishment logic per updated norm
        if total_harvested_round >= 3 * stock_before:
            # Cumulative catch exceeds 300% of starting stock – fully replenish to pre‑fishing weight
            stock_after_regrowth = stock_before
        else:
            # Below threshold – lake stays depleted (no regrowth)
            stock_after_regrowth = stock_after_harvest


        round_record = {
            "round": round_number,
            "phase": "harvest",
            "stock_kg_before": stock_before,
            "reserve_kg_before": 0,
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
            "reserve_kg_after": 0,
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
