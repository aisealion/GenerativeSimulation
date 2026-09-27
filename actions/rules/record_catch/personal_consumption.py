"""
Rule to set personal_consumption_kg = min(total_catch_kg, 1)
"""
from engine.institution.rules import Rule


class PersonalConsumptionRule(Rule):
    """
    Rule that sets personal consumption kg to the minimum of total catch kg and 1 kg.
    """
    type_name = "personal_consumption"

    def __init__(self, key, params):
        super().__init__(key, params)
    
    def after_agent(self, ctx, agent_id, record_entry):
        """
        Apply the rule to compute personal consumption
        """
        # Get the total catch for this agent
        total_catch = record_entry.get('total_catch_kg', 0)
        
        # Compute personal consumption as minimum of catch and 1 kg
        personal_consumption = min(total_catch, 1)
        
        # Return fields to be patched into the record
        return {"personal_consumption_kg": personal_consumption}