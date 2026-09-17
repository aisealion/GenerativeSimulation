from engine.institution.rules import Rule

class CapRule(Rule):
    type_name = "cap_rule"

    def after_agent(self, ctx, agent_id, record_entry):
        # Enforce per-fisher catch cap (default 20kg, configurable via params)
        cap = self.params.get("cap_kg", 20)
        harvested = record_entry.get("harvested_kg", 0)
        if harvested > cap:
            surplus = harvested - cap
            # Trim harvest to cap
            record_entry["harvested_kg"] = cap
            # Record note for fisher
            note = f"Catch trimmed to {cap}kg cap; {surplus:.1f}kg surplus recorded in the reserve."
            record_entry["note"] = (record_entry.get("note", "") + " " + note).strip()
            # Deposit surplus into communal reserve
            ctx.objects.deposit(
                "communal_reserve",
                "balance_kg",
                surplus,
                by_agent_id=agent_id,
                narration=note,
            )
        return None
