from engine.institution.agent_loop import per_agent_decision


def run(ctx):
    state = ctx.state
    runtime = state["runtime"]
    agent_ids = ctx.participants
    
    def build_fields(agent_id):
        # For council to vote on communal pot disbursements
        return {
            "disbursement_options": runtime.get("disbursement_options", []),
        }

    def build_record(agent_id, response):
        return {
            "selected_disbursement": response.get("selected_disbursement", ""),
            "reasoning": response.get("reasoning", ""),
        }

    decisions = per_agent_decision(ctx, build_fields, build_record)
    return {"decisions": decisions}


def memory_writes(state, round_record):
    return [
        {
            "event_type": "disbursement_voted",
            "text": f"voted on disbursement: {decision['selected_disbursement']}",
            "agent_id": agent_id,
            "group_id": "community",
        }
        for agent_id, decision in round_record["decisions"].items()
    ]