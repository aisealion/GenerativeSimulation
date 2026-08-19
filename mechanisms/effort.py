def effort_cap(agent_id, config, fluents, runtime):
    """Return this agent's maximum allowed harvest (kg) for the current round.
    Implements the current norm:

    * Per‑trip limit is 20 kg (or a lower config‑specified cap).
    * If the lake's stock is below 30 kg, fishing is prohibited (cap = 0).
    * Config overrides ``effort_caps_kg`` (per‑agent) and ``default_effort_cap_kg``
      (global) retain precedence when stock permits.
    """
    # Check stock threshold first; if below 30 kg, no fishing allowed.
    stock = runtime.get("stock_kg", 0)
    if stock < 30:
        return 0

    # Config‑based overrides retain priority when stock is sufficient
    caps = config.get("effort_caps_kg", {})
    if agent_id in caps:
        # Ensure the configured cap does not exceed the norm's per‑trip limit
        return min(caps[agent_id], 20.0)
    if "default_effort_cap_kg" in config:
        return min(config["default_effort_cap_kg"], 20.0)

    # Apply the norm‑based per‑trip limit of 20 kg
    return 20.0



def catch_from_effort(effort, stock_kg, config):
    """Linear Schaefer-style catch equation (catch = effort x stock x
    catchability), matching Gupta et al.'s CPRAgent.harvest() —
    ostrom3/Agent.py on origin/hiromu/llm-norm in the Gupta/CPRG_fishing
    repo. effort is the agent's own [0.0, 1.0] fishing-intensity choice;
    config["harvest_productivity"] is their catchability coefficient q."""
    productivity = config.get("harvest_productivity", 1.0)
    return effort * stock_kg * productivity
