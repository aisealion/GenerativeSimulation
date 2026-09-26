from engine.institution.agent_loop import per_agent_decision
from roles.roles import set_fact, end_fact
from engine.institution.rules import Rule

def run(ctx):
    state = ctx.state
    runtime = state["runtime"]
    fluents = state["fluents"]
    round_number = ctx.round_number

    runtime.setdefault("caught_kg", {})
    runtime.setdefault("logbook", [])

    def build_fields(agent_id):
        # Get the catch data from the previous harvest
        previous_harvest = [r for r in runtime["rounds"] if r["action"] == "harvest"][-1] if runtime.get("rounds") else None
        if previous_harvest:
            # We are looking at the last round's harvest data
            fishers = previous_harvest.get("agents", {})
            # For this example, let's just get one fisher's catch to demonstrate
            if fishers:
                caught_kg = list(fishers.values())[0].get("harvested_kg", 0)
                return {"harvested_kg": caught_kg}
        return {"harvested_kg": 0.0}

    def build_record(agent_id, response):
        actual_weight = response.get("actual_weight_kg", 0.0)
        violations = response.get("violations", [])
        
        # Store the catch info
        runtime["caught_kg"][agent_id] = actual_weight
        
        # Log violations if any
        if violations:
            runtime["logbook"].append({
                "agent_id": agent_id,
                "round": round_number,
                "violations": violations,
                "caught_kg": actual_weight
            })
            
        return {
            "actual_weight_kg": actual_weight,
            "violations": violations,
            "note": response.get("note", "")
        }

    def ineligible_record(agent_id):
        return {
            "actual_weight_kg": 0.0,
            "violations": [],
            "note": "Not eligible to present catch",
        }

    agent_records = per_agent_decision(
        ctx, build_fields, build_record, ineligible_record=ineligible_record,
    )

    return {
        "agents": agent_records,
        "caught_kg": runtime["caught_kg"],
        "logbook": runtime["logbook"]
    }