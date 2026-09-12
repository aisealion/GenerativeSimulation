# Encodes no rule's own logic itself — every per-agent constraint (a cap,
# a reserve, a ban) is a Rule plugin under actions/rules/harvest/,
# activated purely through state["config"]["rules"]["harvest"]; with that
# list empty, this handler is physics only. Uses ctx.rules (a generic
# RuleSet — see engine.institution.rules) the exact same way every other
# action's handler does; nothing about harvest's own eligibility/chaining
# logic is special-cased into the runtime any more. Uses
# engine.institution.agent_loop.per_agent_decision() for the actual
# per-agent loop — the same helper propose.py/vote.py use — only the
# fields/record/after_settle callbacks below are harvest-specific.
#
# Uses roles.roles's set_fact()/end_fact() directly for the "dead" fact —
# not through ctx.events — a death is a genuine interval fact (the agent
# stays dead), the same reason a role or a ban is written this way rather
# than as a point-in-time Event.

from roles.roles import set_fact, end_fact
from engine.institution.agent_loop import per_agent_decision
from engine.physics import (
    catch_from_effort,
    apply_regrowth,
    apply_consumption,
    is_dead,
    available_stock,
    CARRYING_CAPACITY_KG,
)


def run(ctx):
    state = ctx.state
    runtime = state["runtime"]
    fluents = state["fluents"]
    round_number = ctx.round_number

    runtime.setdefault("payoff", {})
    runtime.setdefault("dead_agents", [])
    stock_before = available_stock(runtime)

    def build_fields(agent_id):
        constraints_line = ctx.rules.describe_constraints(ctx, agent_id)
        return {
            "stock_kg": stock_before,
            "carrying_capacity_kg": CARRYING_CAPACITY_KG,
            "constraints_line": f" {constraints_line}" if constraints_line else "",
            "stock_trend": _stock_trend(runtime, state["config"], round_number),
        }

    def build_record(agent_id, response):
        effort = min(1.0, max(0.0, float(response["effort"])))
        raw_kg = catch_from_effort(effort, stock_before)
        return {"effort": effort, "harvested_kg": raw_kg, "reasoning": response.get("reasoning", ""), "note": None}

    def after_settle(agent_id, record_entry):
        new_payoff = apply_consumption(runtime["payoff"].get(agent_id, 0.0), record_entry["harvested_kg"])
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

    def ineligible_record(agent_id):
        return {
            "effort": None, "harvested_kg": 0.0, "reasoning": "",
            "note": ctx.rules.ineligibility_note(ctx, agent_id), "participated": False,
        }

    agent_records = per_agent_decision(
        ctx, build_fields, build_record, ineligible_record=ineligible_record, after_settle=after_settle,
    )

    stock_after_harvest = stock_before - sum(r["harvested_kg"] for r in agent_records.values())
    stock_after_regrowth = apply_regrowth(stock_after_harvest)
    runtime["stock_kg"] = stock_after_regrowth

    # A rule that needs to override the round's own final stock number
    # (a "replenish the lake" trigger, say) does so from its own
    # after_action(ctx, round_record) hook — called generically by
    # ActionRuntime right after this function returns — by writing
    # ctx.state["runtime"]["stock_kg"] and round_record["stock_kg_after_regrowth"]
    # directly; no special override method is needed here for that.
    return {
        "agents": agent_records,
        "stock_kg_before": stock_before,
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
