def check_violation(agent_id, requested_kg, actual_kg, cap):
    """Check if a fisher exceeded their limit for this round.
    Returns True if they violated the limit, False otherwise."""
    if cap is None:
        return False
    return actual_kg > cap


def apply_penalty(agent_id, pending_penalties, actual_kg):
    """Apply pending penalty to this round's actual catch.
    Returns (adjusted_kg, remaining_penalty)."""
    penalty = pending_penalties.get(agent_id, 0)
    if penalty <= 0:
        return actual_kg, 0

    # Deduct penalty from current catch, but not below 0
    adjusted_kg = max(0.0, actual_kg - penalty)
    remaining_penalty = max(0.0, penalty - actual_kg)

    return adjusted_kg, remaining_penalty
