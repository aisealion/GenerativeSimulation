"""
Handles the verification action where the Community Steward checks fisher's hauls.
"""
from actions.rules.verify import apply_verification_rules
import random


def run(ctx):
    """Execute the verification process for fishers."""
    # We'll set up a standard action structure and let the rules handle the logic
    state = ctx.state
    runtime = state["runtime"]
    agent_records = {}
    
    # Get all participating fishers
    participate_policy = ctx.action_spec["participation"]["policy"]
    agents = ctx.get_participating_agents(participate_policy)
    
    # Process each fisher in the verification action
    for agent_id in agents:
        # Simulate verification process
        # 1. Retrieve fisher's recorded log weight (from their harvest record)
        # 2. Measure actual haul weight (at the weigh-station) 
        # 3. Calculate discrepancy
        # 4. Apply the discrepancy threshold logic
        
        # For now, we simulate different harvests to test scenarios
        # In a real simulation this would come from the actual harvest log
        
        # Create a fake harvest record for test purposes
        # We'll use a random approach to make it realistic
        recorded_weight = random.uniform(0.5, 3.0)
        actual_weight = random.uniform(0.5, 3.0)
        
        # Calculate discrepancy percentage
        if recorded_weight > 0:
            discrepancy_percent = abs(actual_weight - recorded_weight) / recorded_weight * 100
        else:
            discrepancy_percent = 0.0
            
        # Determine if discrepancy exceeds 5%
        discrepancy_exceeds_5_percent = discrepancy_percent > 5.0
        
        agent_records[agent_id] = {
            "agent_id": agent_id,
            "verification_result": "completed",
            "discrepancy_exceeds_5_percent": discrepancy_exceeds_5_percent,
            "recorded_weight": recorded_weight,
            "actual_weight": actual_weight,
            "discrepancy_percent": discrepancy_percent,
            "reasoning": f"Verification completed. Discrepancy was {discrepancy_percent:.1f}%. " +
                        "Penalty applied." if discrepancy_exceeds_5_percent else 
                        f"Verification completed. Discrepancy was {discrepancy_percent:.1f}%. No penalty."
        }
        
    # Apply any verification rules that may have been activated
    apply_verification_rules(ctx, agent_records)
    
    return {
        "agents": agent_records,
        "action": "verify"
    }