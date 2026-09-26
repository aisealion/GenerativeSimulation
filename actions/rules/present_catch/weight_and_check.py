from engine.institution.rules import Rule

class WeightAndCheckRule(Rule):
    """
    Rule for weighing catch and checking if it exceeds 10kg.
    """
    type_name = "weight_and_check"

    def after_agent(self, ctx, agent_id, record_entry):
        # Check if fisher caught more than 10kg
        harvested_kg = record_entry.get("harvested_kg", 0.0)
        
        if harvested_kg > 10.0:
            excess = harvested_kg - 10.0
            # Add note about exceeding the limit
            return {
                "note": f"Caught {harvested_kg:.1f}kg, exceeding 10kg limit by {excess:.1f}kg. Excess handling required.",
                "excess_kg": excess
            }
        return None

    def on_agent_settled(self, ctx, agent_id, record_entry):
        # Log the catch info for record keeping via logbook object
        harvested_kg = record_entry.get("harvested_kg", 0.0)
        note = record_entry.get("note", "")
        if harvested_kg > 0:
            # In a real implementation, this would record to the logbook object
            # But for now we'll just check the rule is callable
            pass