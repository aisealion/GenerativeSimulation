from engine.institution.context import ActionContext
from engine.institution.agent_loop import per_agent_decision

def run(ctx: ActionContext) -> dict:
    """
    Handler for recording donations to the council.
    """
    def build_fields(agent_id):
        # Provide data fields needed by agent in prompt
        return {
            "stock_kg": ctx.state["runtime"]["stock_kg"]
        }

    def build_record(agent_id, response):
        donation_amount = response.get("donate_amount_kg", 0)
        return {
            "donate_amount_kg": donation_amount,
            "reasoning": response.get("reasoning", ""),
            "donated": donation_amount > 0
        }
    
    def ineligible_record(agent_id):
        return {
            "donate_amount_kg": 0,
            "reasoning": "Not participating in donate",
            "donated": False
        }

    # Use the established per_agent_decision helper
    agent_records = per_agent_decision(
        ctx, build_fields, build_record, ineligible_record=ineligible_record
    )
    
    return {"agents": agent_records}