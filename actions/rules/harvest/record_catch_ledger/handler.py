from engine.institution.rules import Rule

class RecordCatchLedgerRule(Rule):
    """
    Rule that records catch ledger information for fishers.
    """
    
    type_name = "record_catch_ledger"

    def is_eligible(self, ctx, agent_id) -> bool:
        """All agents are eligible to participate"""
        return True

    def after_agent(self, ctx, agent_id, record_entry) -> dict:
        """
        Record catch ledger entry.
        """
        return {}
        
    def on_agent_settled(self, ctx, agent_id, record_entry):
        """Handle ledger recording completion"""
        pass

    def before_action(self, ctx):
        """Before recording begins - nothing special needed"""
        pass

    def after_action(self, ctx, round_record):
        """After recording ends"""
        pass

    def before_round(self, state, round_number):
        """Before round begins"""
        pass

    def after_round(self, state, round_number):
        """After round ends"""
        pass