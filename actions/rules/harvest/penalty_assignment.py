from engine.institution.rules import Rule
from engine.institution.context import ActionContext

class PenaltyAssignmentRule(Rule):
    """Rule that assigns 5-minute penalty for non-compliant fishing activities."""
    
    type_name = "penalty_assignment"
    
    def __init__(self, key: str, params: dict) -> None:
        self.key = key
        self.params = params

    def on_harvest_completed(self, ctx: ActionContext):
        # Check if the fisher was non-compliant during inspection
        compliance_status = ctx.params.get("compliance_status")
        if compliance_status == "Non-compliant":
            # Record excess in communal ledger
            try:
                ledger = ctx.objects.get_object("communal_ledger")
                if ledger:
                    # Add penalty record
                    penalty_record = {
                        "type": "penalty",
                        "penalty_type": "5-minute_community_work",
                        "amount": 5,
                        "timestamp": str(ctx.current_time)
                    }
                    ledger.entries.append(penalty_record)
                    ctx.objects.update_object("communal_ledger", ledger)
                
                # Assign 5-minute community work penalty  
                # The system would track penalties differently, this just tracks the event
                ctx.add_fact("assigned_5min_penalty", True)
            except Exception as e:
                # Log or handle error but don't break execution
                pass