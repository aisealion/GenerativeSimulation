from engine.institution.rules import Rule

class fisher_allowance_rule(Rule):
    type_name = "fisher_allowance_rule"

    def calculate_allowance(self, agent_id, runtime, agents):
        """Calculate fisher's baseline allowance as 10% of biomass B"""
        stock_kg = runtime["stock_kg"]
        return stock_kg * 0.1