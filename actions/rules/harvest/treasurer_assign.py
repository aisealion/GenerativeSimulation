from engine.institution.rules import Rule
from roles.roles import assign_role

class TreasurerAssignRule(Rule):
    type_name = "treasurer_assign"
    description = "Assign rotating treasurer based on the first fisher who logged their catch each day"

    def after_agent(self, ctx, agent_id, record_entry):
        # Store the first logger's id in rule_state if not already set
        state = ctx.rule_state("treasurer_assign")
        if "first_logger" not in state:
            state["first_logger"] = agent_id
        return record_entry

    def after_action(self, ctx, round_record):
        state = ctx.rule_state("treasurer_assign")
        first = state.get("first_logger")
        if first:
            # Assign treasurer role exclusively to the first logger for next round
            assign_role(
                "treasurer",
                first,
                ctx.state["fluents"],
                ctx.round_number + 1,
                exclusive=True,
                narration=f"{first} has been appointed rotating treasurer for the next day.",
                visibility="public",
            )
        # Reset for next day
        ctx.rule_state("treasurer_assign").clear()
        return round_record
