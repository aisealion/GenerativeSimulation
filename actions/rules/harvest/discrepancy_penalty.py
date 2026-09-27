from engine.institution.rules import Rule

class DiscrepancyPenalty(Rule):
    """
    Penalty for Discrepancy - A weight discrepancy over 5% triggers a review; 
    the fisher must give an extra unit to the community pool.
    """
    
    type_name = "discrepancy_penalty"
    
    def after_agent(self, ctx, agent_id, record_entry):
        """
        Process penalties for discrepancies exceeding 5%.
        """
        # This rule processes the verification results that were set by the verify action
        # and applies penalties if discrepancy exceeds 5%
        
        # Check if this agent has a verification result from the verify step
        # The verify action is responsible for calculating the disparity and 
        # setting a flag in the context or in agent record
        if "discrepancy_exceeds_5_percent" in record_entry:
            # If discrepancy exceeds 5%, we apply penalty (extra unit to community pool)
            if record_entry["discrepancy_exceeds_5_percent"]:
                return {
                    "extra_unit_penalty": True,
                    "penalty_amount": 1.0
                }
                
        return {}
        
    def after_action(self, ctx, round_record):
        """
        Process all penalties for the round after action execution.
        """
        # This processes any verification results from the verify action 
        # and applies penalties according to the 5% threshold
        
        # In a realistic implementation, we'd get the verification results 
        # but for now, we're focused on the proper structure
        pass