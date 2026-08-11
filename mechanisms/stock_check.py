def available_stock(runtime):
    return runtime["stock_kg"]


def apply_regrowth(stock_kg, config):
    regrowth = config.get("regrowth_kg_per_round", 0)
    carrying_capacity = config.get("carrying_capacity_kg", stock_kg + regrowth)
    return min(stock_kg + regrowth, carrying_capacity)
