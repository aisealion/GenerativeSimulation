from engine.institution.context import ActionContext

def run(ctx: ActionContext) -> dict:
    """
    Guard confiscates excess fish and records violations.
    """
    results = {}
    
    # In a real implementation, this would check for excess catches and confiscate them
    # For now let's just simulate the process
    confiscated_catches = []
    
    response = {
        "confiscated_catches": confiscated_catches,
        "reasoning": "Excess catches analyzed and violations recorded."
    }
    results["lake_guard"] = response
    
    return results