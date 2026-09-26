from engine.institution.agent_loop import per_agent_decision


def run(ctx):
    state = ctx.state
    runtime = state["runtime"]
    agent_ids = ctx.participants
    
    def build_fields(agent_id):
        # For elder to order surplus catchers to provide additional contribution
        return {
            "surplus_needed": runtime.get("surplus_needed", 0),
            "catch_amount": runtime.get("catch_amount", 0),
        }

    def build_record(agent_id, response):
        return {
            "contribution_amount": response.get("contribution_amount", 0),
            "reasoning": response.get("reasoning", ""),
        }

    decisions = per_agent_decision(ctx, build_fields, build_record)
    return {"decisions": decisions}


def memory_writes(state, round_record):
    return [
        {
            "event_type": "contribution_ordered",
            "text": f"ordered {decision['contribution_amount']}kg additional contribution",
            "agent_id": agent_id,
            "group_id": agent_id,
        }
        for agent_id, decision in round_record["decisions"].items()
        if decision.get("contribution_amount", 0) > 0
    ]