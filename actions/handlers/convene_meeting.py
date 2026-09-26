from engine.institution.agent_loop import per_agent_decision


def run(ctx):
    state = ctx.state
    runtime = state["runtime"]
    agent_ids = ctx.participants
    
    def build_fields(agent_id):
        # For elder convening meeting and community voting on penalties
        # Generate penalty options based on runtime configuration
        # This allows both monetary and labor penalties to be evaluated
        # The specific threshold implementation would be in the rule, not here
        penalty_options = []
        
        # Add typical penalty options - the actual penalty types are determined by system logic
        # This ensures the meeting can handle both monetary and labor penalties
        penalty_options = ["monetary_penalty", "labor_shift"]
        
        return {
            "penalty_options": penalty_options,
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
            "event_type": "meeting_convened",
            "text": f"meeting convened with penalty options: {', '.join(decision['selected_penalty'] for decision in round_record['decisions'].values() if decision.get('selected_penalty'))}",
            "agent_id": agent_id,
            "group_id": "community",
        }
        for agent_id, decision in round_record["decisions"].items()
    ]