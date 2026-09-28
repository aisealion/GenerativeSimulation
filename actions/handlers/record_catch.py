from engine.institution.context import ActionContext
from engine.institution.agent_loop import per_agent_decision

def run(ctx: ActionContext) -> dict:
    """
    Handler for recording catch amount on dock ledger.
    """
    def build_fields(agent_id):
        # Provide data fields needed by agent in prompt
        return {
            "stock_kg": ctx.state["runtime"]["stock_kg"]
        }

    def build_record(agent_id, response):
        catch_amount = response.get("catch_amount_kg", 0)
        return {
            "catch_amount_kg": catch_amount,
            "reasoning": response.get("reasoning", ""),
            "recorded": True
        }
    
    def ineligible_record(agent_id):
        return {
            "catch_amount_kg": 0,
            "reasoning": "Not participating in record_catch",
            "recorded": False
        }

    # Use the established per_agent_decision helper
    agent_records = per_agent_decision(
        ctx, build_fields, build_record, ineligible_record=ineligible_record
    )
    
    return {"agents": agent_records}