from engine.institution.rules import Rule
from roles.roles import set_fact

class AttendanceRule(Rule):
    type_name = "attendance_rule"

    def after_agent(self, ctx, agent_id, record_entry):
        # record_entry contains the answer under key defined in output field, likely "attended"
        answer = record_entry.get("attended", "").strip().lower()
        if answer == "yes":
            set_fact(ctx.state.get('fluents', []), "attended_meeting", [agent_id], agent_id, ctx.round_number,
                     narration=f"{agent_id} attended council meeting.", visibility="public")
        return None
