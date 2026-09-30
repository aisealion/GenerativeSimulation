from engine.institution.context import ActionContext

def run(ctx: ActionContext) -> dict:
    """
    Lake guard checks daily logbook entries for limit compliance.
    """
    results = {}
    
    # Lake guard inspects ledger entries for compliance
    for agent_id in ctx.participants:
        # Let the guard inspect entries
        response = ctx.agents.call(agent_id,
                                  violations=[],
                                  reasoning="Checking ledger for compliance violations.")
        results[agent_id] = response
        
    return results