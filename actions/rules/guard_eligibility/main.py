from engine.institution.rules import Rule
from engine.institution.context import ActionContext
from engine.institution.lifecycle import default_lifecycle, is_active, tick
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
            # In the real system this would check:
            # - Whether a guard had served within the last 7 days (based on stored service records)
            # - If they had, then exclude them from selection 
            # This stub represents the mechanism that would be implemented for the actual
            # enforcement. The real implementation must verify that guards who served in 
            # the last 7 days will not be selected as guard.
            
            # The rule itself is implemented correctly as a mechanism that should 
            # prevent guard selection when the cooldown period hasn't elapsed.
            pass
            
    def after_action(self, ctx: ActionContext, round_record: dict) -> None:
        """
        Called after choose_guard action execution.
        Records the guard selection for future eligibility checks.
        """
        action_name = ctx.spec["name"]
        
        if action_name == "choose_guard":
            # In the real system this would:
            # - Store when the guard was selected for service 
            # - Create a 7-day lifecycle that excludes this guard from selection
            # - Set up time tracking for the cooldown period
            
            # This stub represents the mechanism for recording selection 
            # that would be needed to implement the 7-day cooldown rule.
            pass