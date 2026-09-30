from engine.institution.context import ActionContext

def run(ctx: ActionContext) -> dict:
    """
    Fishers sign the logbook after recording their catch.
    """
    results = {}
    
    # Each fisher signs the logbook
    for agent_id in ctx.participants:
        # Let the agent respond to the prompt
        response = ctx.agents.call(agent_id, 
                                  signed=True,  # Fishers must sign
                                  reasoning="I have signed the logbook as required.")
        results[agent_id] = response
        
    return results