# Reads: state/config.json (effort caps), state/fluents.json (role holders),
# engine/physics.py (fixed catch/regrowth/consumption rates).
# Writes: state/runtime.json (today's catch, payoff, deaths), state/fluents.json (deaths).

from mechanisms.effort import effort_cap
from mechanisms.stock_check import available_stock
from mechanisms.roles import set_fact, end_fact, role_holder
from engine.physics import (
    catch_from_effort,
    apply_regrowth,
    apply_consumption,
    is_dead,
    alive_agent_ids,
    CARRYING_CAPACITY_KG,
)
from engine.llm_agents import call_fisher_agent
from engine.phase_base import Phase


class HarvestPhase(Phase):
    name = "harvest"

    def prompt_fields(self, state, agent_id):
        config = state["config"]
        fluents = state["fluents"]
        runtime = state["runtime"]
        round_number = state["round_number"]
        cap = effort_cap(agent_id, config, fluents, runtime)
        cap_line = (
            f" You currently have an agreed limit of {cap:.0f}kg for this trip."
            if cap is not None
            else ""
        )
        return {
            "stock_kg": available_stock(runtime),
            "carrying_capacity_kg": CARRYING_CAPACITY_KG,
            "cap_line": cap_line,
            "stock_trend": self._stock_trend(runtime, config, round_number),
        }

    def _stock_trend(self, runtime, config, round_number):
        """A short recent-history readout of surveyed stock levels, oldest
        to most recent — lets a fisher notice for themselves whether the
        lake has been recovering or shrinking, the same way Gupta et al.'s
        CPRAgent prompt gives a rolling `resource_history` window rather
        than stating the regrowth rate outright (never named or quantified
        here — no "growth_rate", no formula, just what a fisher would
        actually observe trip to trip). Window size matches
        render_history()'s own `history_window_rounds` so both readouts
        cover the same span of rounds."""
        window = config.get("history_window_rounds", 5)
        past_harvests = [
            r for r in runtime["rounds"]
            if r["phase"] == "harvest" and r["round"] < round_number
        ][-window:]
        if not past_harvests:
            return "This is the first count anyone's taken — no earlier surveys to compare against."
        levels = ", ".join(f"{r['stock_kg_after_regrowth']:.0f}kg" for r in past_harvests)
        return f"The last few counts, oldest to most recent, were: {levels}."

    def run(self, state):
        config = state["config"]
        fluents = state["fluents"]
        runtime = state["runtime"]
        agents = state["agents"]
        round_number = state["round_number"]

        runtime.setdefault("payoff", {})
        runtime.setdefault("dead_agents", [])

        # Process expired bans: end any ban that has served 2 rounds
        for record in list(fluents):
            if record["fluent"] == "ban" and record["terminated_round"] is None:
                if record["initiated_round"] + 2 <= round_number:
                    end_fact(fluents, "ban", record["args"], round_number)

        stock_before = available_stock(runtime)
        # If lake reserve below minimum, halt fishing this round
        if stock_before < config.get("reserve_min_kg", 0):
            set_fact(
                fluents,
                "fishing_halted",
                [],
                "community",
                round_number,
                narration=f"Fishing halted this round because lake reserve ({stock_before:.0f}kg) fell below the minimum of {config.get('reserve_min_kg')}kg.",
                visibility="public",
            )
            results = {}
            # No harvest, just apply regrowth
            stock_after_harvest = stock_before
            stock_after_regrowth = apply_regrowth(stock_after_harvest)
            round_record = {
                "round": round_number,
                "phase": "harvest",
                "stock_kg_before": stock_before,
                "agents": {},
                "stock_kg_after_harvest": stock_after_harvest,
                "stock_kg_after_regrowth": stock_after_regrowth,
            }
            runtime["round"] = round_number
            runtime["stock_kg"] = stock_after_regrowth
            runtime["rounds"].append(round_record)
            return round_record

        for agent_id in alive_agent_ids(agents, runtime):
            # Check for active ban
            ban_record = role_holder("ban", agent_id, fluents, round_number)
            if ban_record is not None:
                # Banned agents cannot fish this round
                harvested = 0.0
                # Record that they did not participate
                results[agent_id] = {
                    "effort": 0.0,
                    "harvested_kg": harvested,
                    "reasoning": "Banned from fishing due to prior violation.",
                }
                continue

            response = call_fisher_agent(
                agent_id, round_number, "harvest", **self.prompt_fields(state, agent_id)
            )
            effort = min(1.0, max(0.0, float(response["effort"])))
            harvested = catch_from_effort(effort, stock_before)
            # Enforce catch cap (default 12 kg from config)
            if cap is not None:
                harvested = min(harvested, cap)


            # Detect violation of catch limit and impose 2‑trip ban
            if cap is not None and harvested < catch_from_effort(effort, stock_before):
                # Violation occurred (catch reduced by cap)
                set_fact(
                    fluents,
                    "ban",
                    [agent_id],
                    agent_id,
                    round_number,
                    narration="You have been banned for 2 trips due to exceeding the catch limit.",
                    visibility="public",
                )

            runtime["payoff"][agent_id] = new_payoff

            results[agent_id] = {
                "effort": effort,
                "harvested_kg": harvested,
                "reasoning": response.get("reasoning", ""),
            }

            if is_dead(new_payoff):
                runtime["dead_agents"].append(agent_id)
                name = agents[agent_id]["name"]
                set_fact(
                    fluents, "dead", [agent_id], agent_id, round_number,
                    narration=f"{name} has died — they hadn't been catching enough fish to survive.",
                    visibility="public",
                )
                end_fact(fluents, "fisher", [agent_id], round_number)

        # No proportional rationing here — matches Gupta et al.'s CPRAgent.harvest(),
        # which subtracts each agent's independently-computed catch (all against the
        # same pre-harvest stock) directly, letting the stock go negative if
        # oversubscribed. The existing collapse check below (stock <= 0) is this
        # project's equivalent of their stop-the-simulation condition.
        stock_after_harvest = stock_before - sum(r["harvested_kg"] for r in results.values())
        stock_after_regrowth = apply_regrowth(stock_after_harvest)

        round_record = {
            "round": round_number,
            "phase": "harvest",
            "stock_kg_before": stock_before,
            "agents": {
                agent_id: {
                    "effort": result["effort"],
                    "harvested_kg": result["harvested_kg"],
                    "reasoning": result["reasoning"],
                }
                for agent_id, result in results.items()
            },
            "stock_kg_after_harvest": stock_after_harvest,
            "stock_kg_after_regrowth": stock_after_regrowth,
        }

        runtime["round"] = round_number
        runtime["stock_kg"] = stock_after_regrowth
        runtime["rounds"].append(round_record)
        return round_record


PHASE = HarvestPhase()
