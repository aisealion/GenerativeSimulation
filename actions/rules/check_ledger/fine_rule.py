from engine.institution.rules import Rule

class FineRule(Rule):
    """
    Rule for applying fines for overage catch and consequences for unpaid fines.
    """
    type_name = "fine_rule"
    
    def __init__(self, key, params):
        super().__init__(key=key, params=params)
        self.fine_per_unit = params.get("fine_per_unit", 0.5)
        self.limit = params.get("limit", 2.0)
        
    def before_action(self, ctx):
        # No pre-action check needed
        pass
    
    def after_action(self, ctx, round_record):
        # Apply fines to overage entries
        pass