from engine.institution.rules import Rule

class WeighCatchRule(Rule):
    """
    Rule that handles the weighing of catch action.
    """
    
    type_name = "weigh_catch"

    def is_eligible(self, ctx, agent_id) -> bool:
        """All agents are eligible to participate"""
        return True

    def after_agent(self, ctx, agent_id, record_entry) -> dict:
        """
        Record weighing of catch.
        """
        return {}
        
    def on_agent_settled(self, ctx, agent_id, record_entry):
        """Handle weighing completion"""
        pass

    def before_action(self, ctx):
        """Before weighing begins - nothing special needed"""
        pass

    def after_action(self, ctx, round_record):
        """After weighing ends"""
        pass

    def before_round(self, state, round_number):
        """Before round begins"""
        pass

    def after_round(self, state, round_number):
        """After round ends"""
        pass