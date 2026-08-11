def effort_cap(agent_id, config, fluents, runtime):
    """Returns this agent's max allowed harvest in kg for the current round,
    or None if no cap currently applies."""
    caps = config.get("effort_caps_kg", {})
    if agent_id in caps:
        return caps[agent_id]
    return config.get("default_effort_cap_kg")
