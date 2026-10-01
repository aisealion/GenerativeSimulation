from engine.institution.context import ActionContext

def run(ctx: ActionContext) -> dict:
    """
    Fishers record their catch in the ledger.
    """
    results = {}
    
    # Each fisher records their catch
    for agent_id in ctx.participants:
        # Let the agent respond to the prompt
        response = ctx.agents.call(agent_id, 
                                  catch_count=0,  # Initial value
                                  reasoning="Recording my catch for today.")
        results[agent_id] = response
        
        # In real implementation we would record to ledger
        # For now just simulate the action
        
    return results