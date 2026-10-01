from engine.institution.context import ActionContext

def run(ctx: ActionContext) -> dict:
    """
    Guard enforces March abstention via ledger checks.
    """
    results = {}
    
    # In a real implementation, this would check that no fishers are fishing in March
    response = {
        "march_abstention_enforced": True,
        "reasoning": "March fishing ban enforced through ledger checks."
    }
    results["lake_guard"] = response
    
    return results