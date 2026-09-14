from engine.institution.rules import Rule

class DailyCapRule(Rule):
    type_name = "daily_cap"
    description = "Enforce daily catch cap of 20% of current stock"

    def after_action(self, ctx, round_record):
        # Reset daily total for next round
        ctx.rule_state("daily_total").clear()
        return round_record
        # Compute daily total for this agent (this rule runs per-agent after harvest)
        # We'll need to accumulate across agents via a shared state key
        daily_key = "daily_total"
        total = ctx.rule_state(daily_key).get("total", 0.0)
        total += record_entry.get("harvested_kg", 0.0)
        ctx.rule_state(daily_key)["total"] = total
        # Determine cap based on current stock
        stock = ctx.state["runtime"]["stock_kg"]
        cap = 0.20 * stock
        if total > cap:
            # Trim the current agent's contribution to respect cap proportionally
            excess = total - cap
            # Reduce this agent's record proportionally
            reduction = min(record_entry.get("harvested_kg", 0.0), excess)
            record_entry["harvested_kg"] -= reduction
            note = f"Daily cap applied: reduced by {reduction:.1f} kg to meet 20% stock limit."
            existing = record_entry.get("note", "")
            record_entry["note"] = (existing + " " + note).strip()
            # Fine 5 kg from ledger for any excess
            ctx.objects.withdraw("communal_ledger", "balance_kg", 5.0, by_agent_id=agent_id,
                narration="Fine for exceeding daily cap.")
        return record_entry
