from engine.institution.rules import Rule
from datetime import datetime

class EnforcementPenalty(Rule):
    """
    Enforcement - A fisher exceeding the two-unit limit more than twice in a month 
    must immediately give an extra unit to the community pool.
    
    Also handles R5: Monthly Violation Count - The council resets all monthly violation counts 
    on the first day of each new month.
    """
    
    type_name = "enforcement_penalty"
    
    def after_agent(self, ctx, agent_id, record_entry):
        """
        Process penalties for fishers who exceed the limit more than twice in a month.
        """
        # Check if the harvest violated the net capacity rule
        # If so, increment the violation count for this fisher
        harvested_kg = record_entry["harvested_kg"]
        
        # Get the current month for tracking violations
        round_number = ctx.round_number
        current_month = (round_number - 1) // 30  # Assuming 30 rounds per month
        
        # Initialize violation tracking if needed
        violations = ctx.state["runtime"].get("fisher_violations", {})
        if agent_id not in violations:
            violations[agent_id] = {}
            
        if current_month not in violations[agent_id]:
            violations[agent_id][current_month] = 0
            
        # Increment violation count if the catch exceeded 2 kg
        if harvested_kg > 2.0:
            violations[agent_id][current_month] += 1
            ctx.state["runtime"]["fisher_violations"] = violations
            
        # Process any penalties if violations exceed three times the limit in a month
        # NOTE: The requirement says 'more than twice', but since the penalty should apply
        # only after three violations (not two), we apply it when there are 3+ violations
        total_violations = violations[agent_id][current_month]
        if total_violations >= 3:
            # Apply extra unit penalty (for three violations)
            return {
                "extra_unit_penalty": True,
                "penalty_amount": 1.0  # Give an extra unit to community pool
            }
        return {}
    
    def after_action(self, ctx, round_record):
        """
        Handle monthly reset of violation counts.
        """
        # This should reset violation counts for all fishers at beginning of each month
        # The rule should ensure fishers track their own violations
        round_number = ctx.round_number
        
        # Check if it's the first day of a month (every 30 rounds)
        if (round_number - 1) % 30 == 0:  # First day of the month
            # Reset violation counts
            if "fisher_violations" in ctx.state["runtime"]:
                # Reset to empty tracking for next month
                ctx.state["runtime"]["fisher_violations"] = {}
                
            # Ensure the violation tracking is initialized in the runtime
            if "fisher_violations" not in ctx.state["runtime"]:
                ctx.state["runtime"]["fisher_violations"] = {}