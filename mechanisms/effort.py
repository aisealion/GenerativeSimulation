def effort_cap(agent_id, config, fluents, runtime):
    """Return this agent's maximum allowed harvest (kg) for the current round.
    Implements the updated norm (norm.txt):

    * Per‑trip limit is **2 %** of the current lake stock.
    * Weekly limit is **1.5 kg** per fisher. Excess beyond the weekly allowance
      is added to the restocking reserve and results in a temporary ban for the
      next week.
    * Config can still override per‑agent or default caps via ``effort_caps_kg``
      and ``default_effort_cap_kg`` when they are lower than the norm‑based limits.
    """
    # Check for active ban
    round_number = runtime.get("round", 0)
    bans = runtime.setdefault("banned_until", {})
    if agent_id in bans and round_number < bans[agent_id]:
        return 0.0

    # Current lake stock and per‑trip limit (2% of current stock)
    stock = runtime.get("stock_kg", 0)
    per_trip_limit = 0.02 * stock

    # Weekly tracking
    week_index = (round_number - 1) // 7
    weekly = runtime.setdefault("weekly_catch", {})
    agent_week = weekly.setdefault(agent_id, {})
    week_key = f"week_{week_index}"
    already_caught = agent_week.get(week_key, 0.0)
    weekly_remaining = max(0.0, 1.5 - already_caught)

    # Allowed amount is the minimum of per‑trip and remaining weekly allowance
    allowed = min(per_trip_limit, weekly_remaining)

    # Config‑based overrides retain priority when they are more restrictive
    caps = config.get("effort_caps_kg", {})
    if agent_id in caps:
        allowed = min(caps[agent_id], allowed)
    elif "default_effort_cap_kg" in config:
        allowed = min(config["default_effort_cap_kg"], allowed)

    return allowed
    # Current lake stock
    stock = runtime.get("stock_kg", 0)
    # Initial stock (used for the 7‑day cumulative limit)
    initial_stock = config.get("carrying_capacity_kg", stock)

    # Per‑trip limit (70% of current stock)
    per_trip_limit = 0.70 * stock

    # 7‑day rolling cumulative tracking
    round_number = runtime.get("round", 0)
    # Ensure we have a list of recent harvests per agent
    recent = runtime.setdefault("rolling_7d", {})
    agent_history = recent.setdefault(agent_id, [])
    # Sum of last 6 rounds (excluding current round, which hasn't happened yet)
    prior_cumulative = sum(agent_history[-6:]) if len(agent_history) >= 6 else sum(agent_history)
    cumulative_limit = 3.0 * initial_stock  # 300% of initial stock
    remaining_cumulative = max(0.0, cumulative_limit - prior_cumulative)

    # The allowed amount this trip is the minimum of per‑trip and remaining cumulative
    allowed = min(per_trip_limit, remaining_cumulative)

    # Config‑based overrides retain priority when they are more restrictive
    caps = config.get("effort_caps_kg", {})
    if agent_id in caps:
        allowed = min(caps[agent_id], allowed)
    elif "default_effort_cap_kg" in config:
        allowed = min(config["default_effort_cap_kg"], allowed)

    return allowed



def catch_from_effort(effort, stock_kg, config):
    """Linear Schaefer-style catch equation (catch = effort x stock x
    catchability), matching Gupta et al.'s CPRAgent.harvest() —
    ostrom3/Agent.py on origin/hiromu/llm-norm in the Gupta/CPRG_fishing
    repo. effort is the agent's own [0.0, 1.0] fishing-intensity choice;
    config["harvest_productivity"] is their catchability coefficient q."""
    productivity = config.get("harvest_productivity", 1.0)
    return effort * stock_kg * productivity
