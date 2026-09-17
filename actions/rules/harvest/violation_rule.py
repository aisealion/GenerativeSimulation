from engine.institution.rules import Rule
from roles.roles import set_fact, end_fact

class ViolationRule(Rule):
    type_name = "violation_rule"

    def after_agent(self, ctx, agent_id, record_entry):
        # Determine if a violation occurred (either recorded note about cap excess or missing log)
        violation = False
        note = record_entry.get("note") or ""
        if "surplus" in note.lower():
            violation = True
        # Additional check: if no record (ineligible) already handled elsewhere
        if violation:
            # Update violation count in rule_state
            state = ctx.rule_state(self.key)
            count = state.get("count", 0) + 1
            state["count"] = count
            # Apply penalties based on count
            if count == 1:
                # Warning + 5kg penalty to reserve
                ctx.objects.deposit("communal_reserve", "balance_kg", 5, narration="First violation penalty added to reserve.")
                set_fact(ctx.fluents, "warning", [agent_id], agent_id, ctx.round_number, narration=f"Warning to {agent_id}: first violation.", visibility="public")
            elif count == 2:
                # 30‑day ban + 5kg penalty
                ctx.objects.deposit("communal_reserve", "balance_kg", 5, narration="Second violation penalty added to reserve.")
                set_fact(ctx.fluents, "ban", [agent_id], agent_id, ctx.round_number, narration=f"30‑day ban imposed on {agent_id}.", visibility="public")
            else:
                # Permanent ban via council decision - logged as fact
                set_fact(ctx.fluents, "permanent_ban", [agent_id], agent_id, ctx.round_number, narration=f"Permanent ban considered for {agent_id}.", visibility="public")
        return None
