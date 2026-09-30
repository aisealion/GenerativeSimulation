from engine.institution.rules import Rule
from engine.institution.context import ActionContext


class StockLimit(Rule):
    """Trip denied if lake stock < 1 unit; excess fish returned."""
    
    type_name = "stock_limit"
    
    def is_eligible(self, ctx: ActionContext, agent_id: str) -> bool:
        # Get the current lake stock from the runtime state
        current_stock = ctx.state["runtime"]["stock_kg"]
        
        # If stock is less than 1 unit, deny eligibility (as per norm requirement)
        # Exact threshold is < 1 unit as specified in norm text
        if current_stock < 1.0:
            return False
        return True

    def describe(self, ctx: ActionContext, agent_id: str) -> str:
        current_stock = ctx.state["runtime"]["stock_kg"]
        if current_stock < 1.0:
            return "You cannot fish because lake stock is below 1kg"
        return "You may fish as long as lake stock is at or above 1kg"