# Handler for fisher preparing departure action - this action has no rules in the current implementation
# but exists to serve as a trigger for the daily watchman inspection.

from engine.institution.context import ActionContext
from roles.roles import set_fact
import json

def run(ctx: ActionContext) -> dict:
    """
    Handler for fisher preparing departure.
    This is triggered when a fisher prepares to leave for fishing.
    The actual enforcement inspection happens via the daily_watchman role.
    """
    # This is a simple handler, the real inspection happens during the daily_watchman decision
    
    # Record the event in state for the watchman to process
    state = ctx.state
    runtime = state["runtime"]
    round_number = ctx.round_number
    
    # Create a simple return that indicates the action completed successfully
    return {
        "agents": {}, # No agent-specific data to record, the actual work is done by the watchdog
        "event": "fisher_prepare_departure",
        "timestamp": ctx.current_time
    }