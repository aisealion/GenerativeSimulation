from engine.institution.rules import Rule

class NetCapacity(Rule):
    """
    Net Capacity - A net is considered full when it holds two units (1 kg total). 
    Any further fish caught must be released.
    """
    
    type_name = "net_capacity"
    
    def after_agent(self, ctx, agent_id, record_entry):
        """Trim catch to maximum allowed (2 kg) if needed"""
        # The harvested_kg is from the agent's raw catch
        harvested_kg = record_entry.get("harvested_kg", 0)
        
        # Get the maximum catch allowed (2 kg) from rule parameters
        maximum_catch_kg = self.params.get("maximum_catch_kg", 2.0)
        
        # If the harvested amount exceeds the limit, trim it down
        if harvested_kg > maximum_catch_kg:
            # Create patch to adjust the record
            return {
                "harvested_kg": maximum_catch_kg,
                "note": "Catch trimmed to net capacity limit of 2 kg"
            } 
        
        return {}