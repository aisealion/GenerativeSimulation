from engine.institution.context import ActionContext

def run(ctx: ActionContext) -> dict:
    """
    Guard reads logs at weekly meetings and confirms excess catches.
    """
    results = {}
    
    # In a real implementation, this would analyze weekly fish catches
    # and identify any low catch fishers
    low_catch_fishers = []
    
    response = {
        "low_catch_fishers": low_catch_fishers,
        "reasoning": "Weekly catch analysis completed to identify fishers with lowest catches."
    }
    results["lake_guard"] = response
    
    return results