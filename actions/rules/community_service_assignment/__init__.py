from engine.institution.rules import Rule
from engine.institution.context import ActionContext

class CommunityServiceAssignment(Rule):
    """Rule that assigns community service to fisher with the lowest weekly catch."""
    
    type_name = "community_service_assignment"
    
    def before_action(self, ctx: ActionContext) -> None:
        """Called before weekly_review or assign_community_service actions."""
        action_name = ctx.spec["name"]
        
        if action_name in ["weekly_review", "assign_community_service"]:
            # This rule would validate that the right fisher receives community service
            pass
            
    def after_action(self, ctx: ActionContext, round_record: dict) -> None:
        """Called after community service assignment to track who has it."""
        action_name = ctx.spec["name"]
        
        if action_name == "assign_community_service":
            # In real implementation, this tracks which fisher got community service
            pass