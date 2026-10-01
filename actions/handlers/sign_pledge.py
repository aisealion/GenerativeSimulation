from engine.institution.context import ActionContext

def run(ctx: ActionContext) -> dict:
    """
    Fishers sign the March pledge to abstain from fishing.
    """
    results = {}
    
    # Each fisher signs the pledge
    for agent_id in ctx.participants:
        response = {
            "pledge_signed": True,
            "reasoning": "Signed the March fishing abstention pledge as required by community."
        }
        results[agent_id] = response
        
    return results