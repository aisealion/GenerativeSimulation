from engine.institution.rules import Rule

class ExcessCapRule(Rule):
    """Enforce per-fisher catch limit of 12 kg per trip.
    Any excess is deposited into the communal pot.
    """
    type_name = "excess_cap"

    def after_agent(self, ctx, agent_id, record_entry):
        # record_entry contains harvested_kg from harvest action
        harvested = record_entry.get("harvested_kg", 0.0)
        excess = max(0.0, harvested - 12.0)
        if excess > 0:
            # deposit excess into communal pot object
            ctx.objects.deposit(
                "communal_pot",
                "balance_kg",
                excess,
                by_agent_id=agent_id,
                narration=f"Excess {excess:.2f}kg from fisher {agent_id} deposited into communal pot.",
            )
        # No modification to record_entry needed
        return None
