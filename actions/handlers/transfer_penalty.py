from engine.institution.agent_loop import per_agent_decision

def run(ctx):
    state = ctx.state
    runtime, agents = state["runtime"], state["agents"]
    agent_ids = ctx.participants

    def build_fields(agent_id):
        return {
            "stock_kg": runtime["stock_kg"],
        }

    def build_record(agent_id, response):
        return {
            "penalty_amount": response["penalty_amount"],
            "excess_catch_returned": response["excess_catch_returned"],
            "reasoning": response.get("reasoning", ""),
        }

    results = per_agent_decision(ctx, build_fields, build_record)
    return {"penalties": results}