def apply_penalty(agent_id, violation_count, config, fluents, runtime):
    """Apply penalty for a fisher violating the norm.
    Currently implements: skip next trip (ban for 1 round) per violation.
    """
    # Increment banned trips for the agent
    current = runtime.get('banned_agents', {})
    current[agent_id] = current.get(agent_id, 0) + violation_count
    runtime['banned_agents'] = current
    # Could also reduce effort cap here if needed in future
    return runtime
