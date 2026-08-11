from mechanisms.roles import role_holder


def effort_cap(agent_id, config, fluents, runtime, round_number):
    """Returns this agent's max allowed harvest in kg for the current round,
    or None if no cap currently applies."""
    # Check if moratorium is active and stock is below threshold
    moratorium = role_holder("moratorium_active", "system", fluents, round_number)
    if moratorium:
        threshold = config.get("moratorium_threshold_kg", 0)
        if runtime.get("stock_kg", 0) < threshold:
            return 0

    # Check if agent has permission to fish this round
    can_fish = role_holder("can_fish", agent_id, fluents, round_number)
    if can_fish is None:
        return 0

    # Return the effort cap if set
    caps = config.get("effort_caps_kg", {})
    if agent_id in caps:
        return caps[agent_id]
    return config.get("default_effort_cap_kg")
