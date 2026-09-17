# Rule enforcing repeat offender ban for exceeding 5% cap twice

from engine.institution.rules import Rule
from roles.roles import set_fact

class RepeatOffenderBanRule(Rule):
    type_name = "repeat_offender_ban"

    def after_agent(self, ctx, agent_id, record_entry):
        # Track violations for this agent across rounds via rule_state
        state = ctx.rule_state(self.key)
        state.setdefault("violation_counts", {})
        # Determine if this agent was trimmed this round by checking penalty fact
        trimmed = any(
            f["fluent"] == "percentage_cap_penalty" and agent_id in f.get("args", [])
            for f in ctx.state["fluents"]
        )
        if trimmed:
            state["violation_counts"].setdefault(agent_id, 0)
            state["violation_counts"][agent_id] += 1
            if state["violation_counts"][agent_id] >= 2:
                # impose ban for 3 days
                set_fact(
                    ctx.state["fluents"], "ban", [agent_id], agent_id, ctx.round_number,
                    narration=f"Ban: {agent_id} banned for 3 days due to repeat violations.", visibility="public",
                    event_type="ban_imposed",
                )
        return None
