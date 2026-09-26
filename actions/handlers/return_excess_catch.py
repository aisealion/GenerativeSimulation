from engine.institution.agent_loop import per_agent_decision


def run(ctx):
    state = ctx.state
    agents = state["agents"]
    agent_ids = ctx.participants
    
    def build_fields(agent_id):
        # For a simple decision about returning excess catch
        return {
            "excess_catch_kg": agents[agent_id].get("excess_catch_kg", 0),
            "limit_kg": 0.75,  # As per requirement R2
        }

    def build_record(agent_id, response):
        return {
            "amount_returned_kg": response.get("amount_returned_kg", 0),
            "reasoning": response.get("reasoning", ""),  
        }

    decisions = per_agent_decision(ctx, build_fields, build_record)
    return {"decisions": decisions}


def memory_writes(state, round_record):
    return [
        {
            "event_type": "excess_catch_returned",
            "text": f"returned {decision['amount_returned_kg']}kg of excess catch",
            "agent_id": agent_id,
            "group_id": agent_id,
        }
        for agent_id, decision in round_record["decisions"].items()
        if decision.get("amount_returned_kg", 0) > 0
    ]