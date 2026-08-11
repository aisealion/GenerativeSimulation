# Reads: state/config.json (effort caps), state/fluents.json (role holders).
# Writes: state/runtime.json (today's catch).

from mechanisms.effort import effort_cap
from mechanisms.penalty import check_violation, apply_penalty
from mechanisms.stock_check import available_stock, apply_regrowth, is_fishing_allowed
from llm_agents import call_fisher_agent


def run(state):
    config = state["config"]
    fluents = state["fluents"]
    runtime = state["runtime"]
    agents = state["agents"]
    round_number = state["round_number"]

    stock_before = available_stock(runtime)
    fishing_allowed = is_fishing_allowed(runtime, config)
    requests = {}
    caps = {}

    # Get pending penalties from previous round's violations
    pending_penalties = runtime.get("pending_penalties", {})

    if not fishing_allowed:
        # Lake is below threshold - both fishers abstain
        for agent_id in agents:
            requests[agent_id] = {
                "requested_kg": 0.0,
                "reasoning": "Lake stock is below the 100kg threshold. Abstaining from fishing until the lake recovers."
            }
            caps[agent_id] = 0.0
    else:
        # Fishing is allowed - proceed with normal harvest
        for agent_id in agents:
            cap = effort_cap(agent_id, config, fluents, runtime)
            caps[agent_id] = cap
            cap_line = (
                f" You currently have an agreed limit of {cap:.0f}kg for this trip."
                if cap is not None
                else ""
            )
            # Add penalty info if applicable
            if pending_penalties.get(agent_id, 0) > 0:
                cap_line += f" You owe {pending_penalties[agent_id]:.0f}kg from a previous violation."
            response = call_fisher_agent(
                agent_id,
                round_number,
                "harvest",
                stock_kg=stock_before,
                regrowth_kg=config.get("regrowth_kg_per_round", 0),
                cap_line=cap_line,
            )
            requested = max(0.0, float(response["harvest_kg"]))
            if cap is not None:
                requested = min(requested, cap)
            requests[agent_id] = {"requested_kg": requested, "reasoning": response.get("reasoning", "")}

    total_requested = sum(r["requested_kg"] for r in requests.values())
    if total_requested <= stock_before:
        actual = {agent_id: r["requested_kg"] for agent_id, r in requests.items()}
    else:
        ratio = stock_before / total_requested
        actual = {agent_id: r["requested_kg"] * ratio for agent_id, r in requests.items()}

    # Check for violations and apply penalties
    violations = {}
    for agent_id in agents:
        cap = caps.get(agent_id)
        if cap is not None and cap > 0:
            if check_violation(agent_id, requests[agent_id]["requested_kg"], actual[agent_id], cap):
                violations[agent_id] = True

    # Apply pending penalties from previous rounds
    penalty_kg = config.get("penalty_kg", 10)
    for agent_id in agents:
        if pending_penalties.get(agent_id, 0) > 0:
            adjusted, remaining = apply_penalty(agent_id, pending_penalties, actual[agent_id])
            actual[agent_id] = adjusted
            pending_penalties[agent_id] = remaining

    stock_after_harvest = stock_before - sum(actual.values())
    stock_after_regrowth = apply_regrowth(stock_after_harvest, config)

    # Set up penalties for next round based on current violations
    new_pending_penalties = {}
    for agent_id in agents:
        if violations.get(agent_id, False):
            new_pending_penalties[agent_id] = penalty_kg
        elif pending_penalties.get(agent_id, 0) > 0:
            # Carry over any remaining unpaid penalty
            new_pending_penalties[agent_id] = pending_penalties[agent_id]

    runtime["pending_penalties"] = new_pending_penalties

    round_record = {
        "round": round_number,
        "phase": "harvest",
        "stock_kg_before": stock_before,
        "fishing_allowed": fishing_allowed,
        "agents": {
            agent_id: {
                "requested_kg": requests[agent_id]["requested_kg"],
                "harvested_kg": actual[agent_id],
                "reasoning": requests[agent_id]["reasoning"],
                "limit_kg": caps.get(agent_id),
                "violated": violations.get(agent_id, False),
            }
            for agent_id in agents
        },
        "stock_kg_after_harvest": stock_after_harvest,
        "stock_kg_after_regrowth": stock_after_regrowth,
    }

    runtime["round"] = round_number
    runtime["stock_kg"] = stock_after_regrowth
    runtime["rounds"].append(round_record)
    return round_record
