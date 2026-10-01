from engine.institution.rules import Rule
from typing import Dict, Any


class RuleExcessHandling(Rule):
    """
    Handle excess fish by returning to lake or placing in reserve.
    """
    
    type_name = "excess_handling"
    
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
        return "Excess harvest will be handled by being returned to lake or placed in reserve."

    def after_agent(self, ctx, agent_id, record_entry):
        """Handle excess fish for the agent's record."""
        # This rule is meant to handle excess fish after the limits are enforced
        # The actual reduction of harvest is done by the limit enforcement rule
        return {}
    
    def on_agent_settled(self, ctx, agent_id, record_entry):
        """Handle excess fish placement in reserve after harvest settlement."""
        pass