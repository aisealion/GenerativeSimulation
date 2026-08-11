def available_stock(runtime):
    return runtime["stock_kg"]


def is_fishing_allowed(runtime, config):
    """Check if fishing is allowed based on the lake stock threshold.
    Returns True if stock >= fishing_threshold_kg, False otherwise."""
    threshold = config.get("fishing_threshold_kg", 0)
    return runtime["stock_kg"] >= threshold


def apply_regrowth(stock_kg, config):
    regrowth = config.get("regrowth_kg_per_round", 0)
    carrying_capacity = config.get("carrying_capacity_kg", stock_kg + regrowth)
    return min(stock_kg + regrowth, carrying_capacity)
