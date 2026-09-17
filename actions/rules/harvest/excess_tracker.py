from engine.institution.rules import Rule

class ExcessTrackerRule(Rule):
    """Tracks excess trips per fisher per month and handles monthly pot reset and distribution.
    After each harvest action, it updates counters. At the start of a new month (round % 4 == 1),
    it adds each fisher's accumulated excess to the communal pot, then clears counters.
    It also clears the pot at the end of the month after distribution (handled elsewhere)."""
    type_name = "excess_tracker"

    def after_agent(self, ctx, agent_id, record_entry):
        # Called each fisher after their harvest record is settled.
        harvested = record_entry.get("harvested_kg", 0.0)
        excess = max(0.0, harvested - 12.0)
        if excess <= 0:
            return None
        # Store per-fisher monthly excess amount and trip count in runtime.
        runtime = ctx.state["runtime"]
        month_data = runtime.setdefault("excess_tracker", {"counts": {}, "amounts": {}})
        month_data["counts"][agent_id] = month_data["counts"].get(agent_id, 0) + 1
        month_data["amounts"][agent_id] = month_data["amounts"].get(agent_id, 0.0) + excess
        return None

    def after_action(self, ctx, round_record):
        # Run after each weekly harvest action.
        round_number = ctx.round_number
        # Determine if this is the first week of a month (assuming 4 weeks per month)
        if (round_number % 4) == 1:
            # Month start: add accumulated excess from previous month to pot.
            runtime = ctx.state["runtime"]
            tracker = runtime.get("excess_tracker", {"counts": {}, "amounts": {}})
            for fisher_id, amt in tracker.get("amounts", {}).items():
                if amt > 0:
                    ctx.objects.deposit(
                        "communal_pot",
                        "balance_kg",
                        amt,
                        by_agent_id=fisher_id,
                        narration=f"Monthly excess {amt:.2f}kg from fisher {fisher_id} added to communal pot.",
                    )
            # Reset tracker for new month.
            runtime["excess_tracker"] = {"counts": {}, "amounts": {}}
        return None
