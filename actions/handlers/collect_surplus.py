from engine.institution.agent_loop import per_agent_decision


def run(ctx):
    state = ctx.state
    agents = state["agents"] 
    agent_ids = ctx.participants
    
    def build_fields(agent_id):
        # For collecting surplus catch from each fisher
        return {
            "surplus_kg": agents[agent_id].get("surplus_kg", 0),
        }

    def build_record(agent_id, response):
        return {
            "amount_collected_kg": response.get("amount_collected_kg", 0),
            "reasoning": response.get("reasoning", ""),
        }

    decisions = per_agent_decision(ctx, build_fields, build_record)
    return {"decisions": decisions}


def memory_writes(state, round_record):
    return [
        {
            "event_type": "surplus_collected",
            "text": f"collected {decision['amount_collected_kg']}kg of surplus",
            "agent_id": agent_id,
            "group_id": "community",
        }
        for agent_id, decision in round_record["decisions"].items()
        if decision.get("amount_collected_kg", 0) > 0
    ]