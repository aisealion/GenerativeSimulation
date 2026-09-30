from engine.institution.context import ActionContext

def run(ctx: ActionContext) -> dict:
    # This action seals the containers at the end of the day
    # It's a simple action just for the signaling
    
    agent_id = ctx.agent_id
    # We'll make the steward seal the containers
    
    return {
        "success": True,
        "message": f"Steward {agent_id} sealed the containers"
    }