class CalculateRemainingStockRule:
    """
    Rule to calculate remaining lake stock based on total catch weight.
    Formula: (total catch weight) / (standard volume-area)
    """
    type_name = "calculate_remaining_stock"
    
    def __init__(self, params):
        self.standard_volume_area = params.get("standard_volume_area", 1000.0)  # default volume/area
    
    def check(self, ctx):
        # This rule is deterministic - it checks if remaining stock meets safety threshold
        # Get total catch weight from the community state
        community = ctx.get_fact("community")
        total_catch = community.get("total_catch_weight", 0.0)
        
        # Calculate remaining stock
        if self.standard_volume_area > 0.0:
            remaining_stock = total_catch / self.standard_volume_area
        else:
            remaining_stock = 0.0
            
        # Check if remaining stock meets safety threshold
        safety_threshold = 0.5  # This is an example threshold
        
        # Set fact for elder to know about safety threshold
        stock_threshold_met = remaining_stock >= safety_threshold
        ctx.set_fact("stock_safety_threshold_met", stock_threshold_met)
        
        return True  # Always satisfy the rule (deterministic)