# Handler for recording lake stock at dawn into the communal ledger

def run(ctx):
    """Record the current lake stock in the ledger object.
    Assumes a ledger object with id 'ledger' exists (declared in state/objects.json).
    """
    # Get current stock
    stock = ctx.state.get("runtime", {}).get("stock_kg", 0)
    # Append an entry to the ledger
    try:
        ctx.objects.append("ledger", "entries", {"round": ctx.round_number, "stock_kg": stock})
    except Exception:
        # If objects not set up, silently ignore – this is a minimal stub
        pass
    return {}
