def apply_penalty(agent_id, violation_count, config, fluents, runtime):
    """Apply penalty for a fisher violating the norm.
    Implements a 10% reduction on the fisher's catch weight for the next round per violation.
    Also accrues the penalty amount to a maintenance fund in runtime.
    """
    # Store penalty multiplier; each violation adds a 10% reduction (multiply by 0.9 per violation)
    current = runtime.get('penalty_factors', {})
    factor = current.get(agent_id, 1.0)
    # Apply reduction for each violation
    for _ in range(violation_count):
        factor *= 0.9
    current[agent_id] = factor
    runtime['penalty_factors'] = current
    # Ensure maintenance fund exists
    runtime.setdefault('maintenance_fund', 0.0)
    # Note: actual penalty amount will be calculated when catch is realized
    return runtime
