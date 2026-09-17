# Rule enforcing community daily catch limit of 30% of current stock

from engine.institution.rules import Rule
from roles.roles import set_fact

class DailyCapRule(Rule):
    type_name = "daily_cap"

    def after_action(self, ctx, round_record):
        # Total harvested after trimming by other rules (record_entry values)
        total_harvest = sum(rec.get("harvested_kg", 0) for rec in round_record["agents"].values())
        # Use recorded stock from ledger at dawn
        ledger_entries = ctx.objects.read("ledger", "entries")
        # Find the latest entry for current round
        current_entry = next((e for e in reversed(ledger_entries) if e["round"] == ctx.round_number), None)
        stock = current_entry["stock_kg"] if current_entry else ctx.state["runtime"].get("stock_kg", 0)
        allowed = 0.25 * stock
        if total_harvest > allowed:
            surplus = total_harvest - allowed
            # Reduce lake stock by surplus
            ctx.state["runtime"]["stock_kg"] -= surplus
            # Record excess fact
            set_fact(
                ctx.state["fluents"], "daily_cap_excess", [], "community", ctx.round_number,
                narration=f"Excess catch of {surplus:.2f}kg recorded.", visibility="public",
                event_type="daily_cap_excess",
            )
            # Distribute surplus equally among all fishers as credit (increase payoff)
            agents = ctx.state.get("agents", {}).keys()
            credit = surplus / len(list(agents)) if agents else 0
            for agent_id in agents:
                ctx.state["runtime"].setdefault("payoff", {}).setdefault(agent_id, 0)
                ctx.state["runtime"]["payoff"][agent_id] += credit
                set_fact(
                    ctx.state["fluents"], "daily_cap_credit", [agent_id], agent_id, ctx.round_number,
                    narration=f"Daily cap credit: {credit:.2f}kg added to payoff.", visibility="public",
                    event_type="daily_cap_credit",
                )
        return None
