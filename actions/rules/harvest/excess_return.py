from engine.institution.rules import Rule

class ExcessReturnRule(Rule):
    """
    Rule that returns fish exceeding 10 units to the lake automatically.
    """
    
    type_name = "excess_return" 

    def is_eligible(self, ctx, agent_id) -> bool:
        """All agents are eligible to participate"""
        return True

    def after_agent(self, ctx, agent_id, record_entry) -> dict:
        """
        If recorded catch exceeds 10 units, return the excess to lake.
        """
        # Check if this fisher caught more than 10 units
        catch_amount = record_entry.get("catch_amount_kg", 0)
        
        if catch_amount > 10:
            # Calculate excess amount to return
            excess = catch_amount - 10
            
            # Store excess amount to be returned
            # We'll record this as a note to the fisher
            note = f"Excess {excess:.1f}kg returned to lake. The catch limit is 10kg."
            
            return {
                "note": note,
                "excess_amount": excess
            }
        
        return None
        
    def on_agent_settled(self, ctx, agent_id, record_entry):
        """Handle the final action of returning excess fish to the lake"""
        if "excess_amount" in record_entry and record_entry["excess_amount"] > 0:
            # Return excess fish to the lake
            excess_amount = record_entry["excess_amount"]
            
            # Increase the lake's stock by the excess amount (not just simulate)
            ctx.state["runtime"]["stock_kg"] += excess_amount
            
            # Also record this for visibility in events
            ctx.events.emit("excess_return", {
                "agent_id": agent_id,
                "amount": excess_amount
            }, visibility="GLOBAL")

    def before_action(self, ctx):
        """Before harvest action begins - nothing special needed"""
        pass

    def after_action(self, ctx, round_record):
        """After action ends, update lake stock if needed"""
        pass

    def before_round(self, state, round_number):
        """Before round begins"""
        pass

    def after_round(self, state, round_number):
        """After round ends"""
        pass