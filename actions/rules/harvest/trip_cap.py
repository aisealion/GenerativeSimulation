from engine.institution.rules import Rule

class TripCapRule(Rule):
    type_name = "trip_cap"
    description = "Enforce per-trip catch cap of 15 kg"

    def after_agent(self, ctx, agent_id, record_entry):
        cap = self.params.get("cap_kg", 15.0)
        harvested = record_entry.get("harvested_kg", 0.0)
        if harvested > cap:
            # Trim to cap and note violation
            record_entry["harvested_kg"] = cap
            note = f"Trip cap applied: harvested reduced to {cap:.1f} kg."
            # Append note
            existing = record_entry.get("note") or ""
            record_entry["note"] = (existing + " " + note).strip()
            # Fine 5 kg from ledger
            # Attempt to withdraw fine from communal ledger; if ledger missing, skip fine.
            try:
                ctx.objects.withdraw("communal_ledger", "balance_kg", 5.0, by_agent_id=agent_id,
                    narration=f"Fine for exceeding trip cap applied to {agent_id}.")
            except KeyError:
                # Ledger not present; no fine applied.
                pass
        return record_entry
