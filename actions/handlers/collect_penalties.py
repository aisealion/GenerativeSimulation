from engine.institution.agent_loop import per_agent_decision


def run(ctx):
    state = ctx.state
    runtime = state["runtime"]
    agent_ids = ctx.participants
    
    def build_fields(agent_id):
        # For elder collecting monetary penalties
        return {
            "penalty_amount": runtime.get("penalty_amount", 0),
        }

    def build_record(agent_id, response):
        return {
            "collected_amount": response.get("collected_amount", 0),
            "reasoning": response.get("reasoning", ""),
        }

    decisions = per_agent_decision(ctx, build_fields, build_record)
    return {"decisions": decisions}


def memory_writes(state, round_record):
    return [
        {
            "event_type": "penalty_collected",
            "text": f"collected {decision['collected_amount']} in penalties",
            "agent_id": agent_id,
            "group_id": "community",
        }
        for agent_id, decision in round_record["decisions"].items()
    ]