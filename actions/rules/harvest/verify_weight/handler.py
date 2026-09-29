from engine.institution.rules import Rule

class VerifyWeightRule(Rule):
    """
    Rule that records council verification of ledger entries.
    """
    
    type_name = "verify_weight"

    def is_eligible(self, ctx, agent_id) -> bool:
        """All agents are eligible to participate"""
        return True

    def after_agent(self, ctx, agent_id, record_entry) -> dict:
        """
        Record verification decision.
        """
        return None
        
    def on_agent_settled(self, ctx, agent_id, record_entry):
        """Handle verification completion"""
        pass

    def before_action(self, ctx):
        """Before verification begins - nothing special needed"""
        pass

    def after_action(self, ctx, round_record):
        """After verification ends"""
        pass

    def before_round(self, state, round_number):
        """Before round begins"""
        pass

    def after_round(self, state, round_number):
        """After round ends"""
        pass