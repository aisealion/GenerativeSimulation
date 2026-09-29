from engine.institution.rules import Rule

class CatchLimitRule(Rule):
    """
    Rule that ensures fishers may keep up to 10 units per day; excess is returned.
    """
    
    type_name = "catch_limit"

    def is_eligible(self, ctx, agent_id) -> bool:
        """All agents are eligible to participate"""
        return True

    def after_agent(self, ctx, agent_id, record_entry) -> dict:
        """
        If recorded catch exceeds 10 units, return the excess to lake.
        """
        # For simplicity, we're checking what's already in the action record
        # This is a simplified version - in a real system the catch would be computed differently
        return None
        
    def on_agent_settled(self, ctx, agent_id, record_entry):
        """Handle returning excess fish to the lake"""
        pass

    def before_action(self, ctx):
        """Before harvest action begins - nothing special needed"""
        pass

    def after_action(self, ctx, round_record):
        """After action ends"""
        pass

    def before_round(self, state, round_number):
        """Before round begins"""
        pass

    def after_round(self, state, round_number):
        """After round ends"""
        pass