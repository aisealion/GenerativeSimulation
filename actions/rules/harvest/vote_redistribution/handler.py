from engine.institution.rules import Rule

class VoteRedistributionRule(Rule):
    """
    Rule that allows council members to vote on surplus redistribution.
    """
    
    type_name = "vote_redistribution"

    def is_eligible(self, ctx, agent_id) -> bool:
        """All agents are eligible to participate"""
        return True

    def after_agent(self, ctx, agent_id, record_entry) -> dict:
        """
        Record vote decision.
        """
        return None
        
    def on_agent_settled(self, ctx, agent_id, record_entry):
        """Handle vote completion"""
        pass

    def before_action(self, ctx):
        """Before voting begins - nothing special needed"""
        pass

    def after_action(self, ctx, round_record):
        """After voting ends"""
        pass

    def before_round(self, state, round_number):
        """Before round begins"""
        pass

    def after_round(self, state, round_number):
        """After round ends"""
        pass