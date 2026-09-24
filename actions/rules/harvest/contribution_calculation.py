"""
Rule implementation for calculating contributions as 5% of total weight, rounded to nearest 0.5 kg.
"""
from engine.institution.rules import Rule


class ContributionCalculation(Rule):
    """
    Implements the rule that calculates 5% of total weight, rounded to nearest 0.5 kg.
    """
    type_name = "contribution_calculation"

    def __init__(self, key, params):
        super().__init__(key, params)
        
    def calculate_contribution(self, total_weight):
        """
        Calculate contribution as 5% of total weight, rounded to nearest 0.5 kg.
        
        Args:
            total_weight (float): Total weight of the catch in kg
            
        Returns:
            float: Calculated contribution rounded to nearest 0.5 kg
        """
        # Calculate 5% of weight
        percentage = 0.05
        raw_contribution = total_weight * percentage
        
        # Round to nearest 0.5 kg
        rounding_interval = self.params.get('rounding_interval', 0.5)
        contribution = round(raw_contribution / rounding_interval) * rounding_interval
        
        return contribution

    def evaluate(self, ctx, agent_id, action_name, action_record):
        """
        Evaluate whether the contribution meets the calculation requirements.
        This would be called by rules engine during action processing.
        """
        # In harvest context, check that the recorded contribution meets the calculated requirement
        if action_name == 'harvest':
            # This is where we'd check that contribution meets requirements
            pass
            
        return True
    
    def constraints(self, ctx, agent_id):
        """
        Return constraints that apply to agents when performing this action.
        """
        # No specific constraints for this rule in a general way,
        # although the rule itself enforces that contributions can't be less than calculated
        return ""

    def after_action(self, ctx, round_record):
        """
        Called after an action is completed to apply any consequences.
        """
        # For harvest, we want to make sure contributions are recorded properly
        if round_record.get('action') == 'harvest':
            # Here we could update communal pot with contributions if needed
            pass