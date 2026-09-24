import json
from roles.roles import set_fact, current_holder

def action_handler(agent_id, fluents, round_number, action_params, action_spec):
    """Action handler for fishers to log their catches"""
    
    # Check if they have logged this round already
    catch_log_record_exists = any(
        fact.get("fluent") == "catch_log" and 
        fact.get("args") == [agent_id, round_number] and
        fact.get("terminated_round") is None
        for fact in fluents
    )
    
    if catch_log_record_exists:
        return {
            "outcome": "failure", 
            "narration": "You have already logged your catch for this round.",
            "memory_writes": []
        }
    
    # Log the catch in the community ledger
    catch_amount = action_params.get("catch_kg", 0)
    
    narration = f"Fisherman {agent_id} logged {catch_amount}kg catch for this round."
    
    # Create catch log record
    set_fact(
        fluents, "catch_log", 
        [agent_id, round_number], agent_id, round_number,
        narration=narration,
        visibility="public",
        event_type="catch_logged"
    )
    
    # Memory writes for fisher's awareness of obligation
    memory_writes = [
        {
            "event_type": "fact_initiated",
            "text": f"You have logged your catch of {catch_amount}kg.",
            "agent_id": agent_id,
            "group_id": agent_id
        }
    ]
    
    return {
        "outcome": "success",
        "narration": narration,
        "memory_writes": memory_writes
    }