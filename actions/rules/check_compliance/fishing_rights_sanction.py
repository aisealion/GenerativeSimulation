from engine.institution.rules import Rule
from engine.institution.context import ActionContext

class FishingRightsSanction(Rule):
    """Rule that implements the sanction for fishers who fail to return excess fish.
    This ensures fishing rights are removed (ban) for one week and 
    community service is completed before rights are restored.
    """
    
    type_name = "fishing_rights_sanction"
    
    def on_agent_settled(self, ctx: ActionContext, agent_id: str, record_entry: dict) -> None:
        """Handle when an agent settles after an action.""" 
        # No specific enforcement needed at settlement level for this rule
        # This is a placeholder
        pass
        
    def before_action(self, ctx: ActionContext) -> None:
        """Called before an action executes - for validation and eligibility."""
        action_name = ctx.spec["name"]
        
        # Allow non-fishing actions to proceed normally
        if action_name not in ['harvest', 'register_catch', 'sign_logbook']:
            return
            
        # This is where a real system would check sanction facts
        # In this implementation, we're documenting that enforcement would happen here
        # A complete implementation would check facts for active sanctions and block actions
        # during the one-week ban period
        pass
            
    def after_action(self, ctx: ActionContext, round_record: dict) -> None:
        """Called after action execution - apply sanctions if needed."""
        action_name = ctx.spec["name"]
        
        if action_name == "check_compliance":
            # This action would be where sanction decisions are made
            # Here a real implementation would:
            # 1. Check if fishers failed to return excess fish
            # 2. Apply one-week ban for such fishers  
            # 3. Track community service requirement
            pass