# Reads: state/config.json (effort caps, catchability, capacity), state/fluents.json (role holders).
# Writes: state/runtime.json (today's catch).

from mechanisms.effort import catch_from_effort
from mechanisms.penalty import apply_penalty
import sys
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

        import datetime
        results = {}
        stock_before = available_stock(runtime)
        # Enforce norm: pause fishing if stock below minimum
        if stock_before < 30:
            # Begin pause until stock recovers to 120 kg
            runtime['fishing_paused'] = True
        if runtime.get('fishing_paused') and stock_before < 120:
            # Continue pause
            for agent_id in agents:
                runtime['trip_records'].append({
                    "agent_id": agent_id,
                    "round": round_number,
                    "harvested_kg": 0.0,
                    "excess_kg": 0.0,
                    "banned": False,
                })
                results[agent_id] = {"effort": 0.0, "harvested_kg": 0.0, "reasoning": "Fishing paused due to low stock"}
                runtime['reported_this_round'][agent_id] = True
            # Compute totals (all zero) and return round record
            total_harvested_round = 0.0
            stock_after_harvest = stock_before
            stock_after_regrowth = stock_before
            round_record = {
                "round": round_number,
                "phase": "harvest",
                "stock_kg_before": stock_before,
                "reserve_kg_before": 0,
                "agents": {agent_id: {"effort": 0.0, "harvested_kg": 0.0, "reasoning": "Fishing paused (stock <30 kg)"} for agent_id in agents},
                "stock_kg_after_harvest": stock_after_harvest,
                "stock_kg_after_regrowth": stock_after_regrowth,
                "reserve_kg_after": 0,
            }
            runtime["round"] = round_number
            runtime["stock_kg"] = stock_after_regrowth
            runtime["rounds"].append(round_record)
            # If stock recovered, clear pause flag
            if stock_before >= 120:
                runtime.pop('fishing_paused', None)
            return round_record
        # Close fishing during May (5) and June (6)
        current_month = datetime.datetime.now().month
        if current_month in (5, 6):
            # No harvesting this round for any agent
            for agent_id in agents:
                runtime['trip_records'].append({
                    "agent_id": agent_id,
                    "round": round_number,
                    "harvested_kg": 0.0,
                    "excess_kg": 0.0,
                    "banned": False,
                })
                results[agent_id] = {"effort": 0.0, "harvested_kg": 0.0, "reasoning": "Fishing closed for season"}
            # Compute totals (all zero) and return round record
            total_harvested_round = 0.0
            stock_after_harvest = stock_before
            stock_after_regrowth = stock_before
            round_record = {
                "round": round_number,
                "phase": "harvest",
                "stock_kg_before": stock_before,
                "reserve_kg_before": 0,
                "agents": {
                    agent_id: {
                        "effort": 0.0,
                        "harvested_kg": 0.0,
                        "reasoning": "Fishing closed (May-June)"
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
        # Otherwise continue normal harvesting

        # Reserve is no longer used under the new norm; keep placeholder for compatibility
        reserve_before = 0
        results = {}
        # Tracking of reporting compliance – each fisher must report their catch each round.
        # We'll store a flag in runtime['reported_this_round'] for each agent.
        runtime.setdefault('reported_this_round', {})
        runtime.setdefault('agent_trip_counts', {})
        runtime.setdefault('trip_records', [])  # ledger of trips (ledger)
        runtime.setdefault('recent_catch_kg', [])  # keep last 30 rounds total catch
        runtime.setdefault('last_trip_round', {})
        runtime.setdefault('last_reported_kg', {})
        runtime.setdefault('donation_next_round', {})
        runtime.setdefault('banned_agents', {})
        runtime.setdefault('maintenance_fund', 0.0)

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
                # Apply any penalty factor from prior violations
                penalty_factor = runtime.get('penalty_factors', {}).get(agent_id, 1.0)
                harvested = base_harvest * penalty_factor
                # Apply donation penalty if applicable
                donation = runtime['donation_next_round'].get(agent_id, 0.0)
                if donation:
                    # Ensure we don't deduct more than harvested
                    deduction = min(donation, harvested)
                    harvested -= deduction
                    runtime['maintenance_fund'] = runtime.get('maintenance_fund', 0.0) + deduction
                    # Reset donation after applied
                    runtime['donation_next_round'].pop(agent_id, None)
                
                # Add penalty amount to maintenance fund (existing penalty logic)
                penalty_amount = base_harvest - harvested
                runtime['maintenance_fund'] = runtime.get('maintenance_fund', 0.0) + penalty_amount

        # Harvest phase now allows fishing regardless of stock level, as each fisher keeps all catch.
        # No communal reserve or contribution logic; excess_kg stays zero.
        
                # Enforce per‑trip cap based on new norm: lesser of 0.15% of current stock or 0.15 kg, adjusted quarterly
                # Initialize quarterly adjustment factor if not present
                if 'monthly_quota_factor' not in runtime:
                    runtime['monthly_quota_factor'] = 1.0
                # Quarterly adjustment (every 12 rounds ≈ 3 months)
                if round_number % 12 == 0:
                    if stock_before < 80:
                        runtime['monthly_quota_factor'] += 0.002  # increase quota by 0.2%
                    elif stock_before > 95:
                        runtime['monthly_quota_factor'] -= 0.002  # decrease quota by 0.2%
                base_cap = 0.0015 * stock_before * runtime['monthly_quota_factor']
                cap_limit = min(base_cap, 0.15)
                if harvested > cap_limit:
                    excess = harvested - cap_limit
                    harvested = cap_limit
                    # Apply a one‑month (4‑round) ban for exceeding cap
                    runtime['banned_agents'][agent_id] = runtime['banned_agents'].get(agent_id, 0) + 4
                else:
                    excess = 0.0
                # Deposit 90% of harvested catch into communal fund, fisher keeps 10%
                deposit = harvested * 0.9
                kept = harvested * 0.1
                # Enforce per‑fisher daily cap (3,000,000 kg)
                if kept > 3_000_000:
                    excess_fisher = kept - 3_000_000
                    kept = 3_000_000
                    # Return excess to lake via maintenance fund (or could add to stock later)
                    runtime['maintenance_fund'] = runtime.get('maintenance_fund', 0.0) + excess_fisher
                runtime['maintenance_fund'] = runtime.get('maintenance_fund', 0.0) + deposit
                # Record the kept amount as the actual harvested for stock accounting
                runtime['trip_records'].append({
                    "agent_id": agent_id,
                    "round": round_number,
                    "harvested_kg": kept,
                    "excess_kg": excess,
                    "banned": False,
                })
                # Store result entry for later aggregation
                results[agent_id] = {"effort": effort, "harvested_kg": kept, "reasoning": "Normal harvest"}
                # Check for lower‑catch report without justification (simple heuristic)
                last_report = runtime['last_reported_kg'].get(agent_id)
                if last_report is not None and harvested < last_report:
                    donation_amt = max(0.05 * last_report, 1.0)
                    runtime['donation_next_round'][agent_id] = donation_amt
                    print(f"Agent {agent_id} reported lower catch ({harvested:.2f} < {last_report:.2f}); donation scheduled: {donation_amt:.2f} kg", file=sys.stderr)
                runtime['reported_this_round'][agent_id] = True
                runtime['agent_trip_counts'][agent_id] = runtime['agent_trip_counts'].get(agent_id, 0) + 1
                # Record last reported catch for future comparison
                runtime['last_reported_kg'][agent_id] = harvested


        # Apply reporting compliance penalties
        runtime.setdefault('non_report_counts', {})
        runtime.setdefault('zero_next_round', {})
        for agent_id in agents:
            if not runtime['reported_this_round'].get(agent_id, False):
                # Increment non‑report count
                cnt = runtime['non_report_counts'].get(agent_id, 0) + 1
                runtime['non_report_counts'][agent_id] = cnt
                # Apply penalty for this violation (each non‑report counts as a violation)
                from mechanisms.penalty import apply_penalty
                runtime = apply_penalty(agent_id, 1, config, fluents, runtime)
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
        # Enforce community daily cap (17,000,000 kg). If exceeded, proportionally reduce each fisher's kept catch and return excess to lake (maintenance fund).
        community_cap = 17_000_000
        if total_harvested_round > community_cap:
            excess_total = total_harvested_round - community_cap
            # Proportionally reduce each fisher's kept harvest based on their contribution.
            for agent_id, entry in results.items():
                original = entry["harvested_kg"]
                if original <= 0:
                    continue
                reduction = (original / total_harvested_round) * excess_total
                new_harvest = max(original - reduction, 0)
                # Update result
                entry["harvested_kg"] = new_harvest
                # Adjust runtime trip_records for this agent (find last record and modify harvested_kg)
                for rec in reversed(runtime['trip_records']):
                    if rec['agent_id'] == agent_id and rec['round'] == round_number:
                        rec['harvested_kg'] = new_harvest
                        break
                # Add reduction to maintenance fund (or could be returned to lake)
                runtime['maintenance_fund'] = runtime.get('maintenance_fund', 0.0) + reduction
            # Recompute total after adjustments
            total_harvested_round = sum(r["harvested_kg"] for r in results.values())
        # Remove community cap enforcement – per‑trip cap already applied above
        # Community total cap removed per norm (no communal pool)
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
