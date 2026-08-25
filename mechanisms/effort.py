def effort_cap(agent_id, config, fluents, runtime):
    """Returns this agent's max allowed harvest in kg for the current round,
    or None if no cap currently applies. A norm-imposed ceiling — distinct
    from engine.physics.catch_from_effort()'s "effort" (the agent's own
    [0,1] fishing-intensity choice), applied as a clamp after that function
    runs. catch_from_effort() itself moved to engine/physics.py — it's
    fixed simulation physics, not something a norm changes; this cap is
    the actual lever a norm sets, via state/config.json."""
    caps = config.get("effort_caps_kg", {})
    if agent_id in caps:
        return caps[agent_id]
    return config.get("default_effort_cap_kg")
