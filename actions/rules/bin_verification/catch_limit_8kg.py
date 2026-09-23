from engine.institution.rules import Rule


class CatchLimit8kg(Rule):
    """
    Limit next trip catch to 8kg if penalty enforced.
    """
    type_name = "catch_limit_8kg"

    def is_eligible(self, ctx, agent_id):
        """
        Agents are eligible for the catch limit rule if they've been penalized.
        """
        # Check if this agent previously violated the ledger
        # In a real system, we'd check history here
        return True

    def describe(self, ctx, agent_id):
        """
        Return a description of the rule's constraint for this agent.
        """
        return "Your catch is limited to 8kg if a penalty has been enforced."

    def before_action(self, ctx):
        """
        Before processing harvest: check and apply the catch limit if needed.
        """
        pass

    def after_agent(self, ctx, agent_id, record_entry):
        """
        Apply catch limitation if the agent has been penalized.
        """
        # Check if this agent had a penalty in a previous round
        # This is a simplified version - in a real system, it would check
        # the agent's history of violations and penalties  
        return None

    def on_agent_settled(self, ctx, agent_id, record_entry):
        """
        When an agent's record is fully settled.
        """
        # This would be where we might actually enforce the 8kg limit
        pass