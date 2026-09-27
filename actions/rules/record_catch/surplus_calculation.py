"""
Rule to calculate surplus_kg = max(0, total_catch_kg - 1)
"""
from engine.institution.rules import Rule


class SurplusCalculationRule(Rule):
    """
    Rule that computes surplus kg = max(0, total_catch_kg - 1)
    """
    type_name = "surplus_calculation"

    def __init__(self, key, params):
        super().__init__(key, params)
    
    def after_agent(self, ctx, agent_id, record_entry):
        """
        Apply the rule to compute surplus
        """
        # Get the total catch for this agent
        total_catch = record_entry.get('total_catch_kg', 0)
        
        # Compute surplus as max of zero and (catch - 1)
        surplus = max(0, total_catch - 1)
        
        # Return fields to be patched into the record
        return {"surplus_kg": surplus}