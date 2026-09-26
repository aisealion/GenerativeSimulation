from engine.institution.agent_loop import per_agent_decision


def run(ctx):
    state = ctx.state
    runtime = state["runtime"]
    agent_ids = ctx.participants
    
    def build_fields(agent_id):
        # Decision for elder to decide second trips 
        return {
            "stock_kg": runtime["stock_kg"],
            "min_stock_threshold": 1000.0,  # Example threshold
        }

    def build_record(agent_id, response):
        return {
            "authorized_second_trip": response.get("authorized_second_trip", False),
            "reasoning": response.get("reasoning", ""),
        }

    decisions = per_agent_decision(ctx, build_fields, build_record)
    return {"decisions": decisions}


def memory_writes(state, round_record):
    return [
        {
            "event_type": "second_trip_decision",
            "text": f"authorized second trip: {decision['authorized_second_trip']}",
            "agent_id": agent_id,
            "group_id": "community",
        }
        for agent_id, decision in round_record["decisions"].items()
    ]