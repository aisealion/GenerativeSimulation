from engine.institution.rules import Rule

class FineEnforcementRule(Rule):
    """
    Rule for enforcing that excess units result in fines.
    """
    type_name = "fine_enforcement"
    
    def __init__(self, key, params):
        super().__init__(key=key, params=params)
        self.fine_per_unit = params.get("fine_per_unit", 0.5)
        self.limit = params.get("limit", 2.0)
    
    def after_agent(self, ctx, agent_id, record_entry):
        # Check if this catch entry exceeds the limit
        if 'harvested_kg' in record_entry:
            harvested = record_entry['harvested_kg']
            if harvested > self.limit:
                excess = harvested - self.limit
                fine_amount = excess * self.fine_per_unit
                # Add fine info to the record
                if 'notes' not in record_entry:
                    record_entry['notes'] = []
                record_entry['notes'].append(f"Fine of {fine_amount} units applied for {excess} excess units.")
                return record_entry
        return record_entry
    
    def on_agent_settled(self, ctx, agent_id, record_entry):
        # Track fines and potentially update ledger for pool allocation
        pass