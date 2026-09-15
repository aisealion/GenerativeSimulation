from engine.institution.rules import Rule

class DailyCapRule(Rule):
    type_name = "daily_cap"
    description = "Enforce daily community catch cap of 100 kg"

    def after_agent(self, ctx, agent_id, record_entry):
        # Track cumulative daily total in rule_state
        state = ctx.rule_state("daily_cap")
        total = state.get("total", 0.0)
        harvested = record_entry.get("harvested_kg", 0.0)
        total += harvested
        state["total"] = total
        cap = 100.0  # fixed daily community cap
        if total > cap:
            # Excess amount over cap
            excess = total - cap
            # Reduce this agent's contribution proportionally
            reduction = min(harvested, excess)
            record_entry["harvested_kg"] = harvested - reduction
            note = f"Daily cap applied: reduced by {reduction:.1f} kg to meet 100kg limit."
            existing = record_entry.get("note", "")
            record_entry["note"] = (existing + " " + note).strip()
            # Deposit excess into communal ledger (if exists)
            try:
                ctx.objects.deposit("communal_ledger", "balance_kg", reduction, by_agent_id=agent_id,
                    narration="Excess catch deposited to communal ledger by daily cap rule.")
            except Exception:
                pass
        return record_entry
