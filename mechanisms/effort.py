def effort_cap(agent_id, config, fluents, runtime):
    """Returns this agent's max allowed harvest in kg for the current round, or ``None``
    if no cap applies. Implements the updated norm:

    * Per‑trip limit is the lesser of 7 % of the lake's current biomass and a weekly
      cap of 8 kg. Config overrides ``effort_caps_kg`` (per‑agent) and
      ``default_effort_cap_kg`` (global) still take precedence.
    """
    # Config‑based overrides retain priority
    caps = config.get("effort_caps_kg", {})
    if agent_id in caps:
        return caps[agent_id]
    if "default_effort_cap_kg" in config:
        return config["default_effort_cap_kg"]

    # Apply the norm‑based calculation
    stock = runtime.get("stock_kg", 0)
    percent_cap = 0.07 * stock  # 7 % of current biomass
    weekly_cap = 8.0  # kg per week (treated as per‑trip cap for simplicity)
    return min(percent_cap, weekly_cap)



def catch_from_effort(effort, stock_kg, config):
    """Linear Schaefer-style catch equation (catch = effort x stock x
    catchability), matching Gupta et al.'s CPRAgent.harvest() —
    ostrom3/Agent.py on origin/hiromu/llm-norm in the Gupta/CPRG_fishing
    repo. effort is the agent's own [0.0, 1.0] fishing-intensity choice;
    config["harvest_productivity"] is their catchability coefficient q."""
    productivity = config.get("harvest_productivity", 1.0)
    return effort * stock_kg * productivity
