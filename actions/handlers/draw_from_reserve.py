from engine.institution.agent_loop import per_agent_decision


def run(ctx):
    state = ctx.state
    runtime = state["runtime"]
    agent_ids = ctx.participants
    
    def build_fields(agent_id):
        # For elder to decide whether to draw from reserve
        return {
            "reserve_balance": runtime.get("reserve_balance", 0),
            "required_amount": runtime.get("required_amount", 0),
        }

    def build_record(agent_id, response):
        return {
            "draw_from_reserve": response.get("draw_from_reserve", False),
            "reasoning": response.get("reasoning", ""),
        }

    decisions = per_agent_decision(ctx, build_fields, build_record)
    return {"decisions": decisions}


def memory_writes(state, round_record):
    return [
        {
            "event_type": "reserve_draw",
            "text": f"used reserve balance: {decision['draw_from_reserve']}",
            "agent_id": agent_id,
            "group_id": "community",
        }
        for agent_id, decision in round_record["decisions"].items()
    ]