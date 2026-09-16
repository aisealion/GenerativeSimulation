from engine.institution.rules import Rule

class SeasonalQuotaRule(Rule):
    type_name = "seasonal_quota"
    description = "Enforce per-trip cap based on seasonal reference stock and handle fines and reserve deposits"

    def after_agent(self, ctx, agent_id, record_entry):
        # Ensure reference stock is recorded in runtime; if missing, default to current stock
        reference_stock = ctx.state["runtime"].get("reference_stock_kg")
        if reference_stock is None:
            reference_stock = ctx.state["runtime"].get("stock_kg", 0.0)
            ctx.state["runtime"]["reference_stock_kg"] = reference_stock
        # Compute 10% cap of reference stock
        cap = reference_stock * 0.10
        harvested = record_entry.get("harvested_kg", 0.0)
        excess = max(0.0, harvested - cap)
        if excess > 0:
            # Reduce harvested to cap
            record_entry["harvested_kg"] = cap
            # Fine is 0.5 kg per kg excess, added to reserve (ledger)
            fine = excess * 0.5
            note = f"Seasonal cap applied: harvested reduced to {cap:.1f} kg. Fine of {fine:.1f} kg added to reserve."
            existing = record_entry.get("note") or ""
            record_entry["note"] = (existing + " " + note).strip()
            # Deposit fine into communal ledger
            try:
                ctx.objects.deposit("communal_ledger", "balance_kg", fine, by_agent_id=agent_id,
                    narration=f"Fine for exceeding seasonal cap by {agent_id}.")
            except Exception:
                pass
        return record_entry

    def after_action(self, ctx, round_record):
        # On first round, store initial reference stock if not already set
        if ctx.round_number == 1 and "reference_stock_kg" not in ctx.state["runtime"]:
            ctx.state["runtime"]["reference_stock_kg"] = ctx.state["runtime"].get("stock_kg", 0.0)
        # At end of season (assume round_number marks end?), check biomass threshold
        # Here we treat every round as potential end; if stock falls below 30% of reference, draw from reserve
        reference_stock = ctx.state["runtime"].get("reference_stock_kg")
        if reference_stock:
            current_stock = ctx.state["runtime"].get("stock_kg", 0.0)
            if current_stock < 0.3 * reference_stock:
                # Determine amount available in reserve
                try:
                    from engine.institution.objects import ObjectRuntime
                    # Read current reserve balance
                    obj_rt = ctx.objects
                    reserve_balance = obj_rt.read("communal_ledger", "balance_kg", viewer_agent_id=None) or 0.0
                    needed = reference_stock * 0.3 - current_stock
                    draw_amount = min(reserve_balance, needed)
                    if draw_amount > 0:
                        # Withdraw from reserve and add to stock
                        ctx.objects.withdraw("communal_ledger", "balance_kg", draw_amount, by_agent_id=None,
                            narration="Seasonal draw from reserve due to low stock.")
                        ctx.state["runtime"]["stock_kg"] = current_stock + draw_amount
                except Exception:
                    pass
        return round_record
