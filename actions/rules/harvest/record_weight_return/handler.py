from engine.institution.rules import Rule

class RecordWeightReturnRule(Rule):
    """
    Rule that records return of excess weight to communal reserve.
    """
    
    type_name = "record_weight_return"

    def is_eligible(self, ctx, agent_id) -> bool:
        """All agents are eligible to participate"""
        return True

    def after_agent(self, ctx, agent_id, record_entry) -> dict:
        """
        Record weight return.
        """
        return {}
        
    def on_agent_settled(self, ctx, agent_id, record_entry):
        """Handle weight return completion"""
        pass

    def before_action(self, ctx):
        """Before return recording begins - nothing special needed"""
        pass

    def after_action(self, ctx, round_record):
        """After return recording ends"""
        pass

    def before_round(self, state, round_number):
        """Before round begins"""
        pass

    def after_round(self, state, round_number):
        """After round ends"""
        pass