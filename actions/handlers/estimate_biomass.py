from engine.institution.agent_loop import per_agent_decision

def run(ctx):
    state = ctx.state
    runtime, agents = state["runtime"], state["agents"]
    agent_ids = ctx.participants

    # Get the latest round harvest to compute the biomass estimation
    last_harvest = next(r for r in reversed(runtime["rounds"]) if r["action"] == "harvest")

    def build_fields(agent_id):
        return {
            "stock_kg": runtime["stock_kg"],
        }

    def build_record(agent_id, response):
        return {
            "decision": response["decision"],
            "reasoning": response.get("reasoning", ""),
        }

    decisions = per_agent_decision(ctx, build_fields, build_record)
    return {"decisions": decisions}