from engine.institution.rules import Rule
from engine.institution.context import ActionContext
import random

class TieBreaking(Rule):
    """Rule that resolves tie in lowest catch by random draw."""
    
    type_name = "tie_breaking"
    
    def before_action(self, ctx: ActionContext) -> None:
        """Called before actions that might result in ties."""
        action_name = ctx.spec["name"]
        
        if action_name == "assign_community_service":
            # In real system, this rule would ensure that if there's a tie,
            # it gets resolved by random draw
            pass
            
    def after_action(self, ctx: ActionContext, round_record: dict) -> None:
        """Called after assignment to ensure tie is broken if needed."""
        action_name = ctx.spec["name"]
        
        if action_name == "assign_community_service":
            # In real system, this would handle the actual tie-breaking logic
            pass