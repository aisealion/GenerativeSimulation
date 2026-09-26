from engine.institution.rules import Rule
from roles.roles import set_fact, end_fact

class CatchThresholdRule(Rule):
    """
    If catch exceeds 10 kg, record and handle excess.
    """
    type_name = "catch_threshold"

    def before_action(self, ctx):
        # Initialize any needed tracking
        pass

    def after_agent(self, ctx, agent_id, record_entry):
        # Check if this catch exceeds 10kg
        harvested_kg = record_entry.get("harvested_kg", 0.0)
        if harvested_kg > 10.0:
            # Log the excess catch
            # We'll store violation info in the runtime state
            ctx.state["runtime"].setdefault("excess_violations", {})
            ctx.state["runtime"]["excess_violations"][agent_id] = {
                "amount_kg": harvested_kg,
                "threshold": 10.0,
                "round": ctx.round_number
            }
            
            # Add a note to the record about the excess
            return {
                "note": f"Caught {harvested_kg:.1f}kg, exceeding 10kg threshold. Excess handling options available."
            }
        return None

    def on_agent_settled(self, ctx, agent_id, record_entry):
        # This hook could do additional processing after all rules have processed
        pass