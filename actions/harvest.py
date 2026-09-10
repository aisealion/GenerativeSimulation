# Reads: state/config.json (active norms — state["config"]["norms"]),
# state/fluents.json (role holders), engine/physics.py (fixed catch/regrowth/
# consumption rates). Writes: state/runtime.json (today's catch, payoff,
# deaths, and any active norm's own persistent state under
# runtime["norms"]), state/fluents.json (deaths).
#
# HarvestAction encodes no norm's rule itself — every per-agent constraint (a
# cap, a reserve, a ban) is a Norm plugin under norms/, activated purely
# through state["config"]["norms"]; with that list empty, this action is
# physics only.

from engine.norms.context import HarvestContext
from engine.norms.engine import NormEngine
from roles.roles import set_fact, end_fact
from engine.physics import (
    catch_from_effort,
    apply_regrowth,
    apply_consumption,
    is_dead,
    CARRYING_CAPACITY_KG,
)
from engine.llm_agents import call_fisher_agent
from engine.action_base import SimpleAgentAction


class HarvestAction(SimpleAgentAction):
    name = "harvest"

    def setup(self, state):
        """Built once per real round (see run()'s shared setup_ctx) — the
        public prompt_fields(state, agent_id) contract calls this fresh on
        demand instead, so a preview won't reflect this-round scratch
        state already mutated by earlier agents (a community-wide running
        tally, say) the way run()'s own shared context does."""
        state["runtime"].setdefault("payoff", {})
        state["runtime"].setdefault("dead_agents", [])
        context = HarvestContext.from_state(state)
        norm_engine = NormEngine.from_config(state["config"])
        norm_engine.start_round(context)
        return context, norm_engine

    def is_eligible(self, state, setup_ctx, agent_id):
        context, norm_engine = setup_ctx
        return norm_engine.is_eligible(context, agent_id)

    def ineligible_result(self, state, setup_ctx, agent_id):
        context, norm_engine = setup_ctx
        return {
            "effort": None,
            "harvested_kg": 0.0,
            "reasoning": "",
            "note": norm_engine.ineligibility_note(context, agent_id),
            "participated": False,
        }

    def build_fields(self, state, setup_ctx, agent_id):
        context, norm_engine = setup_ctx
        constraints_line = norm_engine.describe_constraints(context, agent_id)
        return {
            "stock_kg": context.stock_before,
            "carrying_capacity_kg": CARRYING_CAPACITY_KG,
            "constraints_line": f" {constraints_line}" if constraints_line else "",
            "stock_trend": self._stock_trend(state["runtime"], state["config"], state["round_number"]),
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
            if r["action"] == "harvest" and r["round"] < round_number
        ][-window:]
        if not past_harvests:
            return "This is the first count anyone's taken — no earlier surveys to compare against."
        levels = ", ".join(f"{r['stock_kg_after_regrowth']:.0f}kg" for r in past_harvests)
        return f"The last few counts, oldest to most recent, were: {levels}."

    def call_agent(self, agent_id, round_number, fields):
        return call_fisher_agent(agent_id, round_number, self.name, **fields)

    def record_result(self, state, setup_ctx, agent_id, response):
        context, norm_engine = setup_ctx
        runtime, fluents, agents = state["runtime"], state["fluents"], state["agents"]

        effort = min(1.0, max(0.0, float(response["effort"])))
        raw_kg = catch_from_effort(effort, context.stock_before)
        decision = norm_engine.apply(context, agent_id, raw_kg)

        new_payoff = apply_consumption(runtime["payoff"].get(agent_id, 0.0), decision.kept_kg)
        runtime["payoff"][agent_id] = new_payoff

        if is_dead(new_payoff):
            runtime["dead_agents"].append(agent_id)
            name = agents[agent_id]["name"]
            set_fact(
                fluents, "dead", [agent_id], agent_id, state["round_number"],
                narration=f"{name} has died — they hadn't been catching enough fish to survive.",
                visibility="public",
            )
            end_fact(fluents, "fisher", [agent_id], state["round_number"])

        return {
            "effort": effort,
            "harvested_kg": decision.kept_kg,
            "reasoning": response.get("reasoning", ""),
            "note": decision.note,
            "participated": True,
        }

    def after_participants(self, state, setup_ctx, agent_records):
        context, norm_engine = setup_ctx

        # No proportional rationing here — matches Gupta et al.'s CPRAgent.harvest(),
        # which subtracts each agent's independently-computed catch (all against the
        # same pre-harvest stock) directly, letting the stock go negative if
        # oversubscribed. The existing collapse check (stock <= 0) is this
        # project's equivalent of their stop-the-simulation condition.
        stock_after_harvest = context.stock_before - sum(
            r["harvested_kg"] for r in agent_records.values()
        )
        stock_after_regrowth = apply_regrowth(stock_after_harvest)

        norm_engine.end_round(context, agent_records)
        if context.stock_override_kg is not None:
            stock_after_regrowth = context.stock_override_kg

        state["runtime"]["stock_kg"] = stock_after_regrowth

        return {
            "stock_kg_before": context.stock_before,
            "stock_kg_after_harvest": stock_after_harvest,
            "stock_kg_after_regrowth": stock_after_regrowth,
        }


ACTION = HarvestAction()
