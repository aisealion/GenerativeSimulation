from engine.institution.context import ActionContext

def run(ctx: ActionContext) -> dict:
    """
    Guard signs off on community service completion.
    """
    results = {}
    
    # In a real implementation, this would verify that community service was completed
    response = {
        "service_completed": True,
        "reasoning": "Community service completion verified by guardian."
    }
    results["lake_guard"] = response
    
    return results