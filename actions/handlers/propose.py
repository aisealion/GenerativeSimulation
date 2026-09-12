# Not reducible to builtin_handlers.generic_agent_decision because
# build_fields() aggregates across every OTHER participant's last-harvest
# record into `others_summary` — a computation, not a plain lookup — so
# this stays a small custom handler even though propose is otherwise one
# of the simplest actions in the project. Uses
# engine.institution.agent_loop.per_agent_decision() for the actual loop
# (eligibility/call/rule-patch/settle) — same helper harvest.py/vote.py
# use — so a future rule attached to state["config"]["rules"]["propose"]
# has real effect, even though none exists today.

from engine.institution.agent_loop import per_agent_decision


def run(ctx):
    state = ctx.state
    runtime, agents = state["runtime"], state["agents"]
    agent_ids = ctx.participants

    last_harvest = next(r for r in reversed(runtime["rounds"]) if r["action"] == "harvest")

    def build_fields(agent_id):
        others_summary = "\n".join(
            f"- {agents[other_id]['name']} brought in {last_harvest['agents'][other_id]['harvested_kg']:.0f}kg."
            for other_id in agent_ids
            if other_id != agent_id
        )
        return {
            "your_catch_kg": last_harvest["agents"][agent_id]["harvested_kg"],
            "others_summary": others_summary,
            "stock_kg": runtime["stock_kg"],
        }

    def build_record(agent_id, response):
        return {
            "policy": response["policy"],
            "operationalization": response["operationalization"],
            "reasoning": response.get("reasoning", ""),
        }

    proposals = per_agent_decision(ctx, build_fields, build_record)
    return {"proposals": proposals}


def memory_writes(state, round_record):
    return [
        {
            "event_type": "proposal_made",
            "text": f"you proposed: {proposal['policy']}",
            "agent_id": agent_id,
            "group_id": agent_id,
        }
        for agent_id, proposal in round_record["proposals"].items()
        if proposal.get("participated", True)
    ]
