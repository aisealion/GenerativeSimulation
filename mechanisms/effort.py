def effort_cap(agent_id, config, fluents, runtime):
    """Return this agent's maximum allowed harvest (kg) for the current round.
    Implements the updated norm (norm.txt):

    * Per‑trip limit is **70 %** of the current lake stock.
    * Rolling 7‑day cumulative catch per fisher may not exceed **300 %** of the
      lake's **initial stock** (taken from ``config["carrying_capacity_kg"]``).
    * The lake must retain at least **5 %** of its current stock as a reserve –
      enforced later when applying all agents' catches.
    * Config can still override per‑agent or default caps via
      ``effort_caps_kg`` and ``default_effort_cap_kg`` when they are lower than
      the norm‑based limits.
    """
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
