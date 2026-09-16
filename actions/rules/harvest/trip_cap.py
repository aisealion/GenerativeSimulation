from engine.institution.rules import Rule

class TripCapRule(Rule):
    type_name = "trip_cap"
    description = "Enforce per-trip catch cap of 10 kg"

    def after_agent(self, ctx, agent_id, record_entry):
        # Reference stock is the lake biomass before any harvest in the season
        reference_stock = ctx.state["runtime"]["stock_kg"]
        cap = reference_stock * 0.10  # 10% of reference stock
        harvested = record_entry.get("harvested_kg", 0.0)
        if harvested > cap:
            record_entry["harvested_kg"] = cap
            note = f"Trip cap applied: harvested reduced to {cap:.1f} kg."
            existing = record_entry.get("note") or ""
            record_entry["note"] = (existing + " " + note).strip()
            # Fine 5 kg from ledger (if ledger exists)
            try:
                ctx.objects.withdraw("communal_ledger", "balance_kg", 5.0, by_agent_id=agent_id,
                    narration=f"Fine for exceeding trip cap applied to {agent_id}.")
            except Exception:
                pass
        return record_entry
