def effort_cap(agent_id, config, fluents, runtime):
    """Returns this agent's max allowed harvest in kg for the current round,
    or None if no cap currently applies. A norm-imposed ceiling — distinct
    from catch_from_effort()'s "effort" (the agent's own [0,1] fishing-
    intensity choice), applied as a clamp after that function runs."""
    caps = config.get("effort_caps_kg", {})
    if agent_id in caps:
        return caps[agent_id]
    return config.get("default_effort_cap_kg")


def catch_from_effort(effort, stock_kg, config):
    """Linear Schaefer-style catch equation (catch = effort x stock x
    catchability), matching Gupta et al.'s CPRAgent.harvest() —
    ostrom3/Agent.py on origin/hiromu/llm-norm in the Gupta/CPRG_fishing
    repo. effort is the agent's own [0.0, 1.0] fishing-intensity choice;
    config["harvest_productivity"] is their catchability coefficient q."""
    productivity = config.get("harvest_productivity", 1.0)
    return effort * stock_kg * productivity
