from engine.institution.context import ActionContext
from engine.institution.events import Event, Visibility

def run(ctx: ActionContext) -> dict:
    """
    Community chooses the lake guard by rotating draw from volunteers.
    """
    # Check if there are volunteers for guard position
    # This would actually read a volunteer list from the ledger or some state
    
    results = {}
    
    # For now, let's select one of the agents at random - in a proper implementation,
    # this would read from a volunteer list and rotate through them
    for agent_id in ctx.participants:
        # Let the community select a guard
        response = ctx.agents.call(agent_id,
                                  selected_guard=None,
                                  reasoning="Selecting the next guard through community draw.")
        results[agent_id] = response
        
    # Update the state with the current guard info
    try:
        # This is a simplified approach - normally we'd track the rotation
        guard_id = ctx.participants[0] if ctx.participants else "guard_1"
        ctx.state["lake_guard"] = guard_id
        ctx.events.emit(Event(event_type="guard_selected", text=f"Guard selected: {guard_id}", visibility=Visibility.PARTICIPANTS, holder=guard_id))
    except Exception as e:
        ctx.events.emit(Event(event_type="error", text=f"Guard selection error: {str(e)}", visibility=Visibility.PARTICIPANTS))
    
    return results