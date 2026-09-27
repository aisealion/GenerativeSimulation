from engine.institution.rules import Rule

class LedgerValidationRule(Rule):
    """
    Rule for validating ledger entries
    """
    type_name = "ledger_validation"
    
    def __init__(self, key, params):
        super().__init__(key=key, params=params)
    
    def before_action(self, ctx):
        # Any pre-action validations
        pass