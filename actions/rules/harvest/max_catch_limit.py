from engine.institution.rules import Rule
from engine.institution.context import ActionContext


class MaxCatchLimit(Rule):
    """Maximum catch per trip is three units."""
    
    type_name = "max_catch_limit"
    
    def after_agent(self, ctx: ActionContext, agent_id: str, record_entry: dict) -> dict:
        # We want to cap the catch at 3 units if it exceeds this
        entry_catch = record_entry.get("harvested_kg", 0)
        
        if entry_catch > 3.0:
            # Cap the catch at 3 units
            record_entry["harvested_kg"] = 3.0
            record_entry["note"] = f"Exceeded maximum catch limit (3kg). Capped at 3kg."
            
        return record_entry