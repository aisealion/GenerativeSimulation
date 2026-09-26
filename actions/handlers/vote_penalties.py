from engine.institution.agent_loop import per_agent_decision


def run(ctx):
    state = ctx.state
    runtime = state["runtime"]
    agent_ids = ctx.participants
    
    def build_fields(agent_id):
        # For elder to vote on penalties for violations
        return {
            "violation_details": runtime.get("violation_details", ""),
            "penalty_options": runtime.get("penalty_options", []),
        }

    def build_record(agent_id, response):
        return {
            "selected_penalty": response.get("selected_penalty", ""),
            "reasoning": response.get("reasoning", ""),
        }

    decisions = per_agent_decision(ctx, build_fields, build_record)
    return {"decisions": decisions}


def memory_writes(state, round_record):
    return [
        {
            "event_type": "penalty_voted",
            "text": f"voted on penalty: {decision['selected_penalty']}",
            "agent_id": agent_id,
            "group_id": "community",
        }
        for agent_id, decision in round_record["decisions"].items()
    ]