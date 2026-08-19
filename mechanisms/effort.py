def effort_cap(agent_id, config, fluents, runtime):
    """Return this agent's maximum allowed harvest (kg) for the current round.
    Implements the updated norm (norm.txt):

    * Per‑trip limit is 4 % of the current lake biomass.
    * Weekly cumulative catch per fisher may not exceed 2 kg. This function
      returns the remaining allowance for the current trip (zero if the weekly
      quota is already exhausted).
    * Config overrides ``effort_caps_kg`` (per‑agent) and ``default_effort_cap_kg``
      (global) retain precedence when stock permits.
    """
    # Current lake stock
    stock = runtime.get("stock_kg", 0)
    # Weekly tracking: determine week index (7 rounds per week)
    round_number = runtime.get("round", 0)
    week_index = (round_number - 1) // 7
    week_key = f"week_{week_index}"
    week_data = runtime.setdefault("weekly_harvest", {})
    week_record = week_data.setdefault(week_key, {"agents": {}, "total_harvested_kg": 0.0})
    prior_total = week_record["agents"].get(agent_id, 0.0)
    weekly_remaining = max(0.0, 2.0 - prior_total)

    # If no allowance remains, cap is zero
    if weekly_remaining <= 0.0:
        return 0.0

    # Config‑based overrides retain priority when stock is sufficient
    caps = config.get("effort_caps_kg", {})
    max_norm = min(0.04 * stock, weekly_remaining)
    if agent_id in caps:
        return min(caps[agent_id], max_norm)
    if "default_effort_cap_kg" in config:
        return min(config["default_effort_cap_kg"], max_norm)

    # Apply the norm‑based per‑trip limit of 4 % of biomass, limited by weekly allowance
    return max_norm



def catch_from_effort(effort, stock_kg, config):
    """Linear Schaefer-style catch equation (catch = effort x stock x
    catchability), matching Gupta et al.'s CPRAgent.harvest() —
    ostrom3/Agent.py on origin/hiromu/llm-norm in the Gupta/CPRG_fishing
    repo. effort is the agent's own [0.0, 1.0] fishing-intensity choice;
    config["harvest_productivity"] is their catchability coefficient q."""
    productivity = config.get("harvest_productivity", 1.0)
    return effort * stock_kg * productivity
