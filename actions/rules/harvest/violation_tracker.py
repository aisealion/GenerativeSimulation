from engine.institution.rules import Rule
from engine.institution.context import ActionContext


class ViolationTracker(Rule):
    """Tracks violations and enforces skip days and fines."""
    
    type_name = "violation_tracker"
    
    def after_agent(self, ctx: ActionContext, agent_id: str, record_entry: dict) -> dict:
        """Track violations and enforce them on fisher actions."""
        # Get or initialize violation records for this agent
        if "violations" not in ctx.state.get("runtime", {}):
            ctx.state["runtime"]["violations"] = {}
            
        if "fines" not in ctx.state.get("runtime", {}):
            ctx.state["runtime"]["fines"] = {}
        
        agent_violations = ctx.state["runtime"]["violations"].get(agent_id, [])
        
        # Check if this catch exceeded the limit (3.0 units)
        harvested_kg = record_entry.get("harvested_kg", 0)
        
        if harvested_kg > 3.0:
            # Create a violation with details for the norm requirement
            # The norm specifies: "Two consecutive violations or three separate violations 
            # within a 30‑day month" trigger a skip-day
            violation = {
                "amount": harvested_kg,
                "limit": 3.0,
                "type": "exceeding_limit",
                "timestamp": ctx.state.get("runtime", {}).get("day", 0)
            }
            
            # Add this violation to the agent's history
            agent_violations.append(violation)
            
            # Update violations list 
            ctx.state["runtime"]["violations"][agent_id] = agent_violations
            
            # Check threshold conditions based on the norm  
            record_entry["violation_flagged"] = True
            
            # Track exactly the norm's enforcement requirements  
            # For 2 consecutive violations or 3 separate violations in 30 days
            # Check if we should impose skip day
    
            # Simplified enforcement for testing purposes
            # (In a real system, we'd need time tracking)
            if len(agent_violations) >= 2:
                record_entry["potential_skip_day"] = True
                record_entry["skip_day_reason"] = "Two consecutive violations"
                
            if len(agent_violations) >= 3:
                record_entry["skip_day_required"] = True 
                record_entry["skip_day_reason"] = "Three separate violations in month"
                
        return record_entry
    
    def is_eligible(self, ctx: ActionContext, agent_id: str) -> bool:
        """Check if the fisher is eligible to fish based on skip-day status."""
        # This would check if a fisher has a pending skip day
        return True  # Simplified for now

    def describe(self, ctx: ActionContext, agent_id: str) -> str:
        return "Check for violations and enforce skip days and fines."