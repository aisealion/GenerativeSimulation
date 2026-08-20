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
        policy_violations = []  # Track any cap violations for this round
        # Compute norm-imposed cap: 30% of current lake weight
        norm_cap = 0.30 * stock_before
        for agent_id in agents:
            cap = effort_cap(agent_id, config, fluents, runtime)
            response = call_fisher_agent(
                agent_id, round_number, "harvest", **self.prompt_fields(state, agent_id)
            )
            effort = min(1.0, max(0.0, float(response["effort"])) )
            harvested = catch_from_effort(effort, stock_before, config)
            # Apply any effort cap from config
            if cap is not None:
                harvested = min(harvested, cap)
            # Apply policy cap (30% of lake weight)
            if harvested > norm_cap:
                excess = harvested - norm_cap
                # Record violation
                policy_violations.append({
                    "agent_id": agent_id,
                    "excess_kg": excess,
                })
                # Reduce harvest to allowed cap
                harvested = norm_cap
                # Penalty: add 10% of excess to community reserve
                penalty = 0.10 * excess
                config["community_reserve_kg"] = config.get("community_reserve_kg", 0) + penalty
            # Deposit 5% of the (possibly reduced) harvest into community reserve
            deposit = 0.05 * harvested
            config["community_reserve_kg"] = config.get("community_reserve_kg", 0) + deposit
            results[agent_id] = {
                "effort": effort,
                "harvested_kg": harvested,
                "reasoning": response.get("reasoning", ""),
            }


        # No proportional rationing here — matches Gupta et al.'s CPRAgent.harvest(),
        # which subtracts each agent's independently-computed catch (all against the
        # same pre-harvest stock) directly, letting the stock go negative if
        # oversubscribed. The existing collapse check below (stock <= 0) is this
        # project's equivalent of their stop-the-simulation condition.
        stock_after_harvest = stock_before - sum(r["harvested_kg"] for r in results.values())
        # Log any policy violations for downstream phases or analysis
        if policy_violations:
            # Store violations in runtime for visibility
            runtime.setdefault("policy_violations", []).append({
                "round": round_number,
                "violations": policy_violations,
            })
        # Apply regrowth after harvest
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
