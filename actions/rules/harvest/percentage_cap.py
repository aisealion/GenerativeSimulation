# Rule enforcing per-fisher 5% of current stock cap with minimum 1kg

from engine.institution.rules import Rule
from roles.roles import set_fact

class PercentageCapRule(Rule):
    type_name = "percentage_cap"

    def after_agent(self, ctx, agent_id, record_entry):
        # current stock before any harvest this round
        stock = ctx.state["runtime"].get("stock_kg", 0)
        allowed = 0.05 * stock
        # Apply minimum 1kg if allowed >=1kg, otherwise no minimum (norm handles separately)
        if allowed >= 1.0:
            min_allowed = 1.0
        else:
            min_allowed = allowed
        cap = max(allowed, min_allowed)
        harvested = record_entry.get("harvested_kg", 0)
        if harvested > cap:
            excess = harvested - cap
            # trim catch
            record_entry["harvested_kg"] = cap
            # record penalty as fact for visibility
            set_fact(
                ctx.state["fluents"], "percentage_cap_penalty", [agent_id], agent_id, ctx.round_number,
                narration=f"Penalty: {excess:.2f}kg excess returned with 10% fine.", visibility="public",
                event_type="percentage_cap_penalty",
            )
            # store excess+penalty to be added back to lake later via rule state
            caps = ctx.rule_state(self.key)
            caps.setdefault("excess_return", 0.0)
            caps["excess_return"] += excess * 1.10  # 10% penalty added back
        return None
