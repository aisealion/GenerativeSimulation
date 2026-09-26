from engine.institution.agent_loop import per_agent_decision


def run(ctx):
    state = ctx.state
    runtime = state["runtime"]
    agent_ids = ctx.participants
    
    def build_fields(agent_id):
        # For elder deciding how to distribute surplus among fishers 
        return {
            "surplus_amount": runtime.get("surplus_kg", 0),
        }

    def build_record(agent_id, response):
        return {
            "distribution_kg": response.get("distribution_kg", 0),
            "reasoning": response.get("reasoning", ""),
        }

    decisions = per_agent_decision(ctx, build_fields, build_record)
    return {"decisions": decisions}


def memory_writes(state, round_record):
    return [
        {
            "event_type": "surplus_distribution",
            "text": f"distributed {decision['distribution_kg']}kg of surplus",
            "agent_id": agent_id,
            "group_id": agent_id,
        }
        for agent_id, decision in round_record["decisions"].items()
        if decision.get("distribution_kg", 0) > 0
    ]