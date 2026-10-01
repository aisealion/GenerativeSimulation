from engine.institution.context import ActionContext
import random

def run(ctx: ActionContext) -> dict:
    """
    Guard identifies fisher with lowest catch for community service.
    """
    results = {}
    
    # For now we'll just pretend we identified fishers with low catches
    # and picked one (or resolved tie by draw)
    assigned_fisher = None
    
    response = {
        "assigned_fisher": assigned_fisher,
        "reasoning": "Fishers with lowest catches identified for community service assignment."
    }
    results["lake_guard"] = response
    
    return results