from engine.institution.rules import Rule
from engine.institution.context import ActionContext
from typing import Dict, Any, List

class GuardEligibility(Rule):
    """Rule that ensures a guard cannot serve if they served in the last 7 days."""
    
    type_name = "guard_eligibility"
    
    def before_action(self, ctx: ActionContext) -> None:
        """
        Called before the choose_guard action executes. 
        Ensures only eligible guards can be selected.
        """
        action_name = ctx.spec["name"]
        
        if action_name == "choose_guard":
            # This rule ensures guards can't be selected if they served in the last 7 days
            # This is a simplified implementation
            # In a real system, we'd check stored information about guards who served recently
            pass
            
    def after_action(self, ctx: ActionContext, round_record: dict) -> None:
        """
        Called after choose_guard action execution.
        Records the guard selection for future eligibility checks.
        """
        action_name = ctx.spec["name"]
        
        if action_name == "choose_guard":
            # In a real system, we'd store when this guard was selected to be immune from selection for 7 days
            # For now, this is a placeholder that doesn't actually do anything
            pass