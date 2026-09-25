"""
Ledger Keeper consolidates logs within 24 hours and uploads the summary.
"""
from roles.roles import set_fact, end_fact
from engine.institution.agent_loop import per_agent_decision

def run(ctx):
    state = ctx.state
    runtime = state["runtime"]
    fluents = state["fluents"]
    round_number = ctx.round_number

    # Simulating the consolidation of logs by the Ledger Keeper
    # In a real implementation, this would gather logs from the fishers,
    # process them and notify the elders
    
    # For now, we'll just add a fluent entry for logging
    if "ledger" not in runtime:
        runtime["ledger"] = {"entries": []}
    
    # Add a ledger entry for this consolidation
    consolidation_entry = {
        "round": round_number,
        "type": "consolidation",
        "by": ctx.agent_id,
        "details": "Logs consolidated and summary uploaded"
    }
    
    runtime["ledger"]["entries"].append(consolidation_entry)
    
    # Update fluent to indicate that the ledger has been updated
    set_fact(
        fluents, 
        "ledger_updated", 
        [ctx.agent_id], 
        ctx.agent_id, 
        round_number,
        narration="Ledger updated by Ledger Keeper.",
        visibility="public"
    )
    
    # In a more complex implementation:
    # - This action would collect data from fishers
    # - Process and validate the logs
    # - Upload a summary to the ledger
    # - Notify elders of any violations found
    
    return {
        "consolidation_done": True,
        "entries_count": len(runtime["ledger"]["entries"])
    }