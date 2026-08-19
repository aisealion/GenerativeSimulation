def effort_cap(agent_id, config, fluents, runtime):
    """No static effort caps – the norm enforces a 10% harvest cap per day via the HarvestPhase.
    Returns None so HarvestPhase can compute the cap dynamically.
    """
    return None


def catch_from_effort(effort, stock_kg, config):
    """Linear Schaefer-style catch equation (catch = effort x stock x
    catchability), matching Gupta et al.'s CPRAgent.harvest() —
    ostrom3/Agent.py on origin/hiromu/llm-norm in the Gupta/CPRG_fishing
    repo. effort is the agent's own [0.0, 1.0] fishing-intensity choice;
    config["harvest_productivity"] is their catchability coefficient q."""
    productivity = config.get("harvest_productivity", 1.0)
    return effort * stock_kg * productivity
