def role_holder(role_name, agent_id, fluents, round_number):
    for record in fluents:
        if (
            record["fluent"] == role_name
            and record["holder"] == agent_id
            and record["initiated_round"] <= round_number
            and (record["terminated_round"] is None or record["terminated_round"] > round_number)
        ):
            return record
    return None


def assign_role(role_name, agent_id, fluents, round_number, args=None):
    args = args if args is not None else [agent_id]
    for record in fluents:
        if (
            record["fluent"] == role_name
            and record["args"] == args
            and record["terminated_round"] is None
        ):
            record["terminated_round"] = round_number
    fluents.append(
        {
            "fluent": role_name,
            "args": args,
            "holder": agent_id,
            "initiated_round": round_number,
            "terminated_round": None,
        }
    )
    return fluents
