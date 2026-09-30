from engine.institution.context import ActionContext

def run(ctx: ActionContext) -> dict:
    # This action signs the final ledger entry
    # It's a simple action just for the signaling
    
    agent_id = ctx.agent_id
    # We'll make the cook sign the final ledger
    
    return {
        "success": True,
        "message": f"Cook {agent_id} signed the final ledger entry"
    }