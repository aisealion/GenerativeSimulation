from engine.institution.rules import Rule
from roles.roles import set_fact, end_fact

class RepeatViolationBanRule(Rule):
    """
    Repeat violation within 30 days results in ban.
    """
    type_name = "repeat_violation_ban"

    def before_action(self, ctx):
        # Initialize tracking if needed
        pass

    def after_agent(self, ctx, agent_id, record_entry):
        # We'll track violations in a runtime logbook
        return None

    def on_agent_settled(self, ctx, agent_id, record_entry):
        # Check if this agent has violated recently
        runtime = ctx.state["runtime"]
        
        # For simplicity, let's just store information about each violation
        # In a real implementation, this would check recent violations within 30 days
        # and apply the ban if appropriate
        harvested_kg = record_entry.get("harvested_kg", 0.0)
        if harvested_kg > 10.0:
            # Mark that this agent committed a violation
            runtime.setdefault("past_violations", {})
            runtime["past_violations"].setdefault(agent_id, [])
            runtime["past_violations"][agent_id].append({
                "amount_kg": harvested_kg,
                "round": ctx.round_number
            })