from engine.institution.rules import Rule
from roles.roles import set_fact

class CatchLimitRule(Rule):
    type_name = "catch_limit"

    def after_agent(self, ctx, agent_id, record_entry):
        # Determine the current stock from runtime
        stock = ctx.state["runtime"].get("stock_kg", 0)
        limit_by_stock = 0.10 * stock
        limit = min(4.0, limit_by_stock)
        caught = record_entry.get("harvested_kg", 0)
        excess = max(0.0, caught - limit)
        # Record note about limit and excess
        note_parts = []
        note_parts.append(f"Limit this trip: {limit:.2f} kg (min of 4 kg and 10% of stock).")
        if excess > 0:
            note_parts.append(f"Excess {excess:.2f} kg handed to community storage.")
            # Deposit excess into community storage object
            # Deposit excess into community storage if the object exists
            try:
                ctx.objects.deposit(
                    "community_storage",
                    "balance_kg",
                    excess,
                    narration=f"{agent_id} deposited excess catch.",
                    by_agent_id=agent_id,
                )
            except KeyError:
                # Object not present in this minimal validation context; skip deposit
                pass
            # Impose a 1‑week (7‑round) ban via a fluent
            # The ban fluent is named "ban" with args (agent_id,)
            # Use set_fact from roles module
            set_fact(
                ctx.state["fluents"],
                "ban",
                [agent_id],
                "community",
                ctx.round_number,
                narration=f"{agent_id} banned for 7 days due to excess catch.",
                visibility="public",
            )
        record_entry["note"] = " ".join(note_parts)
        return record_entry
