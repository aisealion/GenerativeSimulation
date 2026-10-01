from __future__ import annotations
from typing import Any
from engine.institution.rules import Rule


class AutomaticBanRule(Rule):
    """
    Automatically ban fisher until repayment or task completion.
    """
    
    type_name = "automatic_ban"

    def on_repay_pool_decided(self, ctx, **kwargs):
        # This is the main rule implementation - check if fisher should be banned
        fisher_id = ctx.agent_id
        # Get the repayment status from context
        repayment_made = kwargs.get('repayment_made', False)
        task_completed = kwargs.get('task_completed', False)
        
        # If no repayment and no task completed, ban the fisher
        if not repayment_made and not task_completed:
            # Create ban fluent
            ctx.set_fact("ban", holder="community", args={
                "fisher": fisher_id,
                "reason": "No repayment or task completion",
                "banned": True
            })
    
    def on_assign_helper_task_decided(self, ctx, **kwargs):
        # When a task is assigned, we should update the situation 
        # The rule can record that a task was assigned
        pass
    
    def on_agent_settled(self, ctx, agent_id, record_entry):
        # This rule should respond to agent settling to set up proper initialization
        pass
    
    def on_verify_task_completion_decided(self, ctx, **kwargs):
        # React to task completion verification
        pass