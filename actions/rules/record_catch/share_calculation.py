"""
Rule to compute share_kg = surplus_kg / n and apply to all villagers 
"""
from engine.institution.rules import Rule


class ShareCalculationRule(Rule):
    """
    Rule that divides surplus among living villagers and applies to payoffs
    """
    type_name = "share_calculation"

    def __init__(self, key, params):
        super().__init__(key, params)
    
    def after_action(self, ctx, round_record):
        """
        Apply the rule to compute shares for all agents
        """
        # Count living villagers 
        community = ctx.state.get("community", {})
        population = community.get("population", [])
        
        # Count active villagers (alive)
        living_count = len([v for v in population if v.get('alive', True)])
        
        # If no villagers, no shares
        if living_count == 0:
            return round_record
            
        # Calculate share for each agent and update
        for entry in round_record:
            surplus = entry.get('surplus_kg', 0)
            share = surplus / living_count if living_count > 0 else 0
            entry['share_kg'] = share
            
        return round_record