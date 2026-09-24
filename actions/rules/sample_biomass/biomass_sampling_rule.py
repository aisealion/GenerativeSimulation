from engine.institution.rules import Rule

class biomass_sampling_rule(Rule):
    type_name = "biomass_sampling_rule"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def should_apply_penalty(self, stock_kg, carrying_capacity_kg):
        """
        Determine if biomass is below 10% threshold for penalty.
        """
        if carrying_capacity_kg > 0:
            threshold = carrying_capacity_kg * 0.1
            return stock_kg < threshold
        return False
        
    def calculate_penalty_multiplier(self):
        """
        Return the penalty multiplier (0.95) for biomass below threshold.
        """
        return self.params.get("multiplier", 0.95)
        
    def calculate_compound_multiplier(self, consecutive_violations):
        """
        Calculate compounded multiplier for consecutive violations.
        """
        if consecutive_violations <= 0:
            return 1.0
            
        multiplier = self.params.get("multiplier", 0.95) 
        return multiplier ** consecutive_violations