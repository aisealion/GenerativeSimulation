from engine.institution.agent_loop import per_agent_decision


def run(ctx):
    state = ctx.state
    runtime = state["runtime"]
    agent_ids = ctx.participants
    
    def build_fields(agent_id):
        # Decision for elder to invite volunteers and allocate permits
        return {
            "available_permits": runtime.get("available_permits", 0),
            "total_active_fishers": len(agent_ids),
        }

    def build_record(agent_id, response):
        return {
            "volunteered_for_second_trip": response.get("volunteered_for_second_trip", False),
            "reasoning": response.get("reasoning", ""),
        }

    decisions = per_agent_decision(ctx, build_fields, build_record)
    return {"decisions": decisions}


def memory_writes(state, round_record):
    return [
        {
            "event_type": "volunteer_invitation",
            "text": f"volunteered for second trip: {decision['volunteered_for_second_trip']}",
            "agent_id": agent_id,
            "group_id": "community",
        }
        for agent_id, decision in round_record["decisions"].items()
    ]