import json
from roles.roles import set_fact, assign_role, current_holder
from actions.rules.harvest import calculate_catch_limit

def action_handler(agent_id, fluents, round_number, action_params, action_spec):
    """Action handler for steward presenting monthly catch limit to community"""
    
    # Check if steward is currently assigned
    steward_id = current_holder(fluents, "steward", round_number)
    
    # Make sure the current agent is the steward
    if steward_id != agent_id:
        return {
            "outcome": "failure",
            "narration": "Only the steward can present catch limits.",
            "memory_writes": []
        }
        
    # Calculate biomass and catch limit (for demonstration, we'll use static values)
    # In real implementation, this would come from actual biomass calculations
    biomass = 3000  # kg - lake biomass 
    catch_limit = calculate_catch_limit(biomass, 1)  # 1 month
    
    # Present proposal about the catch limit and lake health metrics
    narration = f"Steward proposing monthly catch limit of {catch_limit}kg with current lake biomass of {biomass}kg."
    
    # Store this proposal as a fact that can be voted on
    set_fact(
        fluents, "catch_limit_proposal", 
        [round_number], steward_id, round_number,
        narration=narration,
        visibility="public",
        event_type="catch_limit_proposed"
    )
    
    # Memory writes for the steward's knowledge of their task
    memory_writes = [
        {
            "event_type": "fact_initiated",
            "text": f"You have calculated the catch limit for this month.",
            "agent_id": agent_id,
            "group_id": agent_id
        }
    ]
    
    return {
        "outcome": "success",
        "narration": narration,
        "memory_writes": memory_writes
    }