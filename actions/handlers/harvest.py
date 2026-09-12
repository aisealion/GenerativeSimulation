# Ported 1:1 from the old actions/harvest.py (a SimpleAgentAction
# subclass) — the per-agent loop SimpleAgentAction.run() used to run
# generically is inlined here explicitly, since harvest's eligibility/
# death/norm-chain logic never fit builtin_handlers.generic_agent_decision's
# much smaller shape (ask one question, record the answer). Uses
# roles.roles's set_fact()/end_fact() directly for the "dead" fact —
# bypassing ctx.events — a deliberate exception preserving the original
# code exactly, not a pattern a new handler should copy without reason.
#
# Encodes no norm's rule itself — every per-agent constraint (a cap, a
# reserve, a ban) is a Norm plugin under norms/, activated purely through
# state["config"]["norms"]; with that list empty, this handler is physics
# only.

from engine.norms.context import HarvestContext
from engine.norms.engine import NormEngine, tick_norm_lifecycles
from roles.roles import set_fact, end_fact
from engine.physics import (
    catch_from_effort,
    apply_regrowth,
    apply_consumption,
    is_dead,
    CARRYING_CAPACITY_KG,
)


def run(ctx):
    state = ctx.state
    runtime = state["runtime"]
    fluents = state["fluents"]
    round_number = ctx.round_number

    runtime.setdefault("payoff", {})
    runtime.setdefault("dead_agents", [])
    tick_norm_lifecycles(state["config"], fluents, round_number)
    context = HarvestContext.from_state(state)
    norm_engine = NormEngine.from_config(state["config"], round_number)
    norm_engine.start_round(context)

    agent_records = {}
    for agent_id in ctx.participants:
        if not norm_engine.is_eligible(context, agent_id):
            agent_records[agent_id] = {
                "effort": None,
                "harvested_kg": 0.0,
                "reasoning": "",
                "note": norm_engine.ineligibility_note(context, agent_id),
                "participated": False,
            }
            continue

        constraints_line = norm_engine.describe_constraints(context, agent_id)
        fields = {
            "stock_kg": context.stock_before,
            "carrying_capacity_kg": CARRYING_CAPACITY_KG,
            "constraints_line": f" {constraints_line}" if constraints_line else "",
            "stock_trend": _stock_trend(runtime, state["config"], round_number),
        }
        response = ctx.agents.call(agent_id, **fields)

        effort = min(1.0, max(0.0, float(response["effort"])))
        raw_kg = catch_from_effort(effort, context.stock_before)
        decision = norm_engine.apply(context, agent_id, raw_kg)

        new_payoff = apply_consumption(runtime["payoff"].get(agent_id, 0.0), decision.kept_kg)
        runtime["payoff"][agent_id] = new_payoff

        if is_dead(new_payoff):
            runtime["dead_agents"].append(agent_id)
            name = state["agents"][agent_id]["name"]
            set_fact(
                fluents, "dead", [agent_id], agent_id, round_number,
                narration=f"{name} has died — they hadn't been catching enough fish to survive.",
                visibility="public",
            )
            end_fact(fluents, "fisher", [agent_id], round_number)

        agent_records[agent_id] = {
            "effort": effort,
            "harvested_kg": decision.kept_kg,
            "reasoning": response.get("reasoning", ""),
            "note": decision.note,
            "participated": True,
        }

    stock_after_harvest = context.stock_before - sum(
        r["harvested_kg"] for r in agent_records.values()
    )
    stock_after_regrowth = apply_regrowth(stock_after_harvest)

    norm_engine.end_round(context, agent_records)
    if context.stock_override_kg is not None:
        stock_after_regrowth = context.stock_override_kg

    runtime["stock_kg"] = stock_after_regrowth

    return {
        "agents": agent_records,
        "stock_kg_before": context.stock_before,
        "stock_kg_after_harvest": stock_after_harvest,
        "stock_kg_after_regrowth": stock_after_regrowth,
    }


def _stock_trend(runtime, config, round_number):
    """A short recent-history readout of surveyed stock levels, oldest to
    most recent — lets a fisher notice for themselves whether the lake has
    been recovering or shrinking, mirroring Gupta et al.'s CPRAgent prompt's
    own rolling resource_history window rather than stating the regrowth
    rate outright."""
    window = config.get("history_window_rounds", 5)
    past_harvests = [
        r for r in runtime["rounds"]
        if r["action"] == "harvest" and r["round"] < round_number
    ][-window:]
    if not past_harvests:
        return "This is the first count anyone's taken — no earlier surveys to compare against."
    levels = ", ".join(f"{r['stock_kg_after_regrowth']:.0f}kg" for r in past_harvests)
    return f"The last few counts, oldest to most recent, were: {levels}."
