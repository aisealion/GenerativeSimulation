def available_stock(runtime):
    return runtime["stock_kg"]


def apply_regrowth(stock_kg, config):
    """Logistic growth on the leftover (post-harvest) stock — matches
    Gupta et al.'s CPRModel.step() (ostrom3/Model.py on
    origin/hiromu/llm-norm in the Gupta/CPRG_fishing repo):
    ΔR = growth_rate * R * (1 - R/capacity), applied to what's left after
    harvest, not a flat per-round add. Growth slows as the stock nears
    carrying capacity and (unlike a flat add) can't outrun a depleted lake."""
    growth_rate = config.get("growth_rate", 0.1)
    carrying_capacity = config.get("carrying_capacity_kg", stock_kg)
    grown = stock_kg + growth_rate * stock_kg * (1 - stock_kg / carrying_capacity)
    return min(grown, carrying_capacity)
