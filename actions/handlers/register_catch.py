from engine.institution.context import ActionContext
from engine.institution.events import Event, Visibility

def run(ctx: ActionContext) -> dict:
    """
    Fishers record their daily catch in the ledger.
    """
    results = {}
    
    # Each fisher records their catch
    for agent_id in ctx.participants:
        # Let the agent respond to the prompt
        response = ctx.agents.call(agent_id, 
                                  catch_count=0,  # Initial value
                                  reasoning="Recording my catch for today.")
        results[agent_id] = response
        
    # Now record the catch in the shared ledger object
    # If shared ledger object exists, record the fisher's catch
    try:
        ledger = ctx.objects.get_object("shared_ledger")
        if ledger:
            for agent_id, response in results.items():
                day = ctx.state["round_number"]  # Using round number as day indicator
                ledger_entry = {
                    "fisher": agent_id,
                    "day": day,
                    "catch": response["catch_count"]
                }
                # Add entry to ledger
                ledger.data["daily_catch_records"].append(ledger_entry)
                # Update the ledger
                ctx.objects.update_object(ledger.id, ledger.data)
                
    except Exception as e:
        # Log the error but don't interrupt the action
        ctx.events.emit(Event(event_type="error", text=f"Catch registration error for {agent_id}: {str(e)}", visibility=Visibility.PARTICIPANTS))
    
    return results