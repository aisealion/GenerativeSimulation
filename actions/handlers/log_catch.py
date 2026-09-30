# Action to log catch entries to shared ledger
from engine.institution.context import ActionContext
from engine.institution.agent_loop import per_agent_decision

def run(ctx: ActionContext) -> dict:
    state = ctx.state
    runtime = state["runtime"]
    fluents = state["fluents"]
    
    # This action is for the cook to log their catch details
    # We'll create a simple per-agent decision that creates ledger entries
    
    def build_fields(agent_id):
        # Fields that the cook needs to provide
        return { 
            "can_log_catch": True,
            "agent_id": agent_id 
        }

    def build_record(agent_id, response):
        # The cook logs catch with timestamp
        catch_amount = float(response.get("catch_amount", 0)) if response.get("catch_amount") else 0.0
        timestamp = response.get("timestamp", "")
        return {
            "catch_amount": catch_amount,
            "timestamp": timestamp,
            "log_entry": f"Catch logged by cook {agent_id}: {catch_amount} units at {timestamp}"
        }

    def after_settle(agent_id, record_entry):
        # Update the shared ledger with the catch entry
        # Here we would access the shared ledger object
        pass
    
    # Note: Using the standard interface but for the actual ledger update we would use 
    # the object system to write the actual ledger entry
    
    # We'll make this simple for now - we're setting up the interface.
    agent_records = per_agent_decision(
        ctx, build_fields, build_record, after_settle=after_settle
    )
    return {
        "agents": agent_records,
        "action": "log_catch"
    }