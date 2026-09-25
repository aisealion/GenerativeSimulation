"""
Elders review the ledger and enforce compliance.
"""
from roles.roles import set_fact, end_fact
from engine.institution.agent_loop import per_agent_decision

def run(ctx):
    state = ctx.state
    runtime = state["runtime"]
    fluents = state["fluents"]
    round_number = ctx.round_number

    # In a more complex implementation, this would:
    # - Review the ledger for violations
    # - Determine what violations were found
    # - Apply consequences for violations
    
    # For now, we'll add a fluent entry indicating elder review
    enforcement_action = {
        "round": round_number,
        "type": "compliance_review",
        "by": ctx.agent_id,
        "details": "Ledger reviewed for compliance"
    }
    
    if "ledger" in runtime:
        runtime["ledger"]["entries"].append(enforcement_action)
    
    # Update fluent to indicate that compliance was enforced
    set_fact(
        fluents, 
        "compliance_enforced", 
        [ctx.agent_id], 
        ctx.agent_id, 
        round_number,
        narration="Compliance enforced by elders.",
        visibility="public"
    )
    
    # In a real implementation:
    # - The elders would analyze the ledger
    # - Identify violations
    # - Apply sanctions or penalties
    # - Notify affected fishers
    
    return {
        "review_done": True,
        "violation_count": 0
    }