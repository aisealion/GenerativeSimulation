from engine.institution.rules import Rule

class TripCapRule(Rule):
    type_name = "trip_cap"
    description = "Enforce per-trip catch cap of 10 kg"

    def after_agent(self, ctx, agent_id, record_entry):
        cap = self.params.get("cap_kg", 10.0)
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
