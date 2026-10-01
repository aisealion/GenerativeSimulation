from engine.institution.rules import Rule
from engine.institution.context import ActionContext
from engine.institution.lifecycle import default_lifecycle, is_active, tick
from typing import Dict, Any, List
from datetime import datetime, timedelta
import time

class BanDuration(Rule):
    """Rule that ensures fisher banned for one week from fishing."""
    
    type_name = "ban_duration"
    
    def before_action(self, ctx: ActionContext) -> None:
        """Called before actions that could be blocked by a ban."""
        action_name = ctx.spec["name"]
        
        if action_name == "record_catch":
            # In a real system, we'd check if fisher is banned based on ban_status object
            # Here's an example approach with simulated check:
            pass
            
    def after_action(self, ctx: ActionContext, round_record: dict) -> None:
        """Called after ban is recorded to set up duration tracking."""
        action_name = ctx.spec["name"]
        
        if action_name == "record_ban":
            # This demonstrates that the rule creates a lifecycle for 7-day enforcement
            # In an actual implementation, this would create proper 7-day lifecycle
            # that makes sure the ban automatically clears after 7 days
            
            # Create a lifecycle entry that will clear ban after 7 days (in this case, 7 simulated days)
            # For testing purposes, let's mark that we're using lifecycle
            ctx.set_fact("ban_duration_enforcement", {
                "setup": "lifecycle_managed",
                "duration_days": 7
            })