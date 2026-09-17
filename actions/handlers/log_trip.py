"""Handler for logging each fisher's trip catch weight immediately after the trip.

Records a public fact for each fisher with their harvested weight from the current round.
"""

from roles.roles import set_fact


def run(ctx):
    """Log each agent's harvested weight from the most recent round record.
    Assumes this action runs after the harvest action in the same round.
    """
    fluents = ctx.state["fluents"]
    round_number = ctx.round_number
    # Get the latest round record (the current round)
    current_round = ctx.state["runtime"]["rounds"][-1]
    agents_records = current_round.get("agents", {})
    for agent_id, record in agents_records.items():
        harvested = record.get("harvested_kg", 0)
        set_fact(
            fluents,
            "trip_logged",
            [agent_id],
            agent_id,
            round_number,
            narration=f"Fisher {agent_id} logged catch weight {harvested:.2f}kg.",
            visibility="public",
            event_type="trip_logged",
        )
    return {}
