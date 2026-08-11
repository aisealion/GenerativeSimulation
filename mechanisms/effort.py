from mechanisms.stock_check import is_fishing_allowed


def effort_cap(agent_id, config, fluents, runtime):
    """Returns this agent's max allowed harvest in kg for the current round.
    Returns 0 if fishing is not allowed (lake below 100kg threshold).
    Returns limit_critical_kg (70) if lake >= 160kg.
    Returns limit_very_high_kg (60) if lake is 140-159kg.
    Returns limit_high_kg (50) if lake is 120-139kg.
    Returns limit_medium_kg (40) if lake is 100-119kg."""
    if not is_fishing_allowed(runtime, config):
        return 0.0

    stock_kg = runtime.get("stock_kg", 0)
    limit_critical_threshold = config.get("limit_critical_threshold_kg", 160)
    limit_critical = config.get("limit_critical_kg", 70)
    limit_very_high_threshold = config.get("limit_very_high_threshold_kg", 140)
    limit_very_high = config.get("limit_very_high_kg", 60)
    limit_high_threshold = config.get("limit_high_threshold_kg", 120)
    limit_high = config.get("limit_high_kg", 50)
    limit_medium = config.get("limit_medium_kg", 40)

    if stock_kg >= limit_critical_threshold:
        return limit_critical
    elif stock_kg >= limit_very_high_threshold:
        return limit_very_high
    elif stock_kg >= limit_high_threshold:
        return limit_high
    else:
        return limit_medium
