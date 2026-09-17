from engine.institution.rules import Rule
from roles.roles import set_fact

class WeightCapRule(Rule):
    type_name = "weight_cap"

    def after_agent(self, ctx, agent_id, record_entry):
        # Enforce 10kg per trip limit
        harvested = record_entry.get("harvested_kg", 0)
        if harvested > 10:
            # Reduce to cap
            record_entry["harvested_kg"] = 10
            # Record infraction
            set_fact(
                ctx.state["fluents"],
                "infraction",
                [agent_id],
                agent_id,
                ctx.round_number,
                narration=f"Infraction: {agent_id} exceeded 10kg catch (caught {harvested:.2f}kg)",
                visibility="public",
                event_type="infraction_recorded",
            )
            # Update count in rule state
            counts = ctx.rule_state("infraction_counts")
            counts.setdefault(str(agent_id), 0)
            counts[str(agent_id)] += 1
            # Issue warning on second infraction
            if counts[str(agent_id)] == 2:
                set_fact(
                    ctx.state["fluents"],
                    "warning",
                    [agent_id],
                    agent_id,
                    ctx.round_number,
                    narration=f"Warning: {agent_id} has received a second infraction.",
                    visibility="public",
                    event_type="warning_issued",
                )
        return None
