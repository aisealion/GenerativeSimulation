from engine.institution.rules import Rule
from roles.roles import set_fact, end_fact

class ViolationRule(Rule):
    type_name = "violation_rule"

    def is_eligible(self, ctx, agent_id):
        # Block harvest if fisher's permission is revoked
        for fact in ctx.state.get('fluents', []):
            if fact["fluent"] == "revoked" and fact["holder"] == agent_id and fact["terminated_round"] is None:
                return False
        return True
    def after_agent(self, ctx, agent_id, record_entry):
        # Determine if a violation occurred (recorded note about cap excess)
        violation = False
        note = record_entry.get("note") or ""
        if "surplus" in note.lower():
            violation = True

        if violation:
            # Update violation count in rule_state
            state = ctx.rule_state(self.key)
            count = state.get("count", 0) + 1
            state["count"] = count

            # Apply penalties based on count
            if count == 1:
                # Warning + 5kg penalty to reserve
                ctx.objects.deposit("communal_reserve", "balance_kg", 5,
                                   narration="First violation penalty added to reserve.")
                set_fact(ctx.state.get('fluents', []), "warning", [agent_id], agent_id,
                         ctx.round_number,
                         narration=f"Warning to {agent_id}: first violation.",
                         visibility="public")
            elif count == 2:
                # 30‑day ban + 5kg penalty
                ctx.objects.deposit("communal_reserve", "balance_kg", 5,
                                   narration="Second violation penalty added to reserve.")
                set_fact(ctx.state.get('fluents', []), "ban", [agent_id], agent_id,
                         ctx.round_number,
                         narration=f"30‑day ban imposed on {agent_id}.",
                         visibility="public")
            elif count == 3:
                # 1‑month revocation + 5kg penalty, require council attendance
                ctx.objects.deposit("communal_reserve", "balance_kg", 5,
                                   narration="Third violation penalty added to reserve.")
                set_fact(ctx.state.get('fluents', []), "revoked", [agent_id], agent_id,
                ctx.round_number,
                narration=f"Fishing permission revoked for {agent_id} after three violations.",
                visibility="public")
            else:
                # Additional violations beyond three keep revocation
                set_fact(ctx.state.get('fluents', []), "revoked", [agent_id], agent_id,
                ctx.round_number,
                narration=f"Fishing permission remains revoked for {agent_id}.",
                visibility="public")
        return None
