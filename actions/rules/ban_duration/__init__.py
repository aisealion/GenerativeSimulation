from engine.institution.rules import Rule
from engine.institution.context import ActionContext

class BanDuration(Rule):
    """Rule that ensures fisher banned for one week from fishing."""
    
    type_name = "ban_duration"
    
    def before_action(self, ctx: ActionContext) -> None:
        """Called before actions that could be blocked by a ban."""
        action_name = ctx.spec["name"]
        
        if action_name == "record_catch":
            # In a real system, this would check if the fisher is banned from fishing
            # and prevent the action if they are
            pass
            
    def after_action(self, ctx: ActionContext, round_record: dict) -> None:
        """Called after ban is recorded to store ban information."""
        action_name = ctx.spec["name"]
        
        if action_name == "record_ban":
            # In real system, this records the ban to be used in future checks
            pass