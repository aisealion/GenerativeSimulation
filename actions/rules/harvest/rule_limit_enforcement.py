from engine.institution.rules import Rule
from typing import Dict, Any


class RuleLimitEnforcement(Rule):
    """
    Enforce 1.5 unit and 10% catch limits during harvest.
    """
    
    type_name = "limit_enforcement"
    
    def __init__(self, key: str, params: dict) -> None:
        super().__init__(key, params)

    def before_action(self, ctx):
        """Called before the harvest action runs."""
        pass

    def after_action(self, ctx, round_record):
        """Called after the harvest action completes."""
        pass

    def is_eligible(self, ctx, agent_id):
        """Check if agent is eligible to harvest."""
        return True

    def describe(self, ctx, agent_id):
        """Provide a description of the constraint for this agent."""
        return "You must not harvest more than 1.5kg or more than 10% of total catch."

    def after_agent(self, ctx, agent_id, record_entry):
        """Apply harvest limits to the agent's record."""
        # Get agent's harvest
        harvested_kg = record_entry.get('harvested_kg', 0)
        
        # Get community stock from state
        # The community stock is in the state["community"] key
        community_state = ctx.state.get('community', {})
        total_stock = community_state.get('stock_kg', 0)
        
        # Apply 1.5kg limit or 10% of total catch, whichever is lower
        limit_15kg = 1.5
        limit_percentage = total_stock * 0.10 if total_stock > 0 else 0
        
        # Calculate the maximum allowed (lower of the two limits)
        max_allowed = min(limit_15kg, limit_percentage) if limit_percentage > 0 else limit_15kg
        
        # If harvest exceeds limits, reduce it
        if harvested_kg > max_allowed:
            new_harvest = max_allowed
            return {
                'harvested_kg': new_harvest
            }
        return {}
    
    def on_agent_settled(self, ctx, agent_id, record_entry):
        """Handle actions after the agent's harvest is settled."""
        pass