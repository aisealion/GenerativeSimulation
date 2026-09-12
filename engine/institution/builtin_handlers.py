# The zero-code execution path for a declarative ActionSpec (Level 2: "a
# new action assembled from existing generic components"). Deliberately
# small in scope — this covers exactly "ask each participating agent one
# question and record their answer" (optionally renaming response fields),
# nothing more. The moment a new action needs a role grant, an
# institutional fact, custom eligibility, or a field computed by
# aggregating across other agents, it needs a small
# actions/handlers/{name}.py instead — that's Level 3, still far smaller
# than a full custom Action subclass used to be, never a cliff back to
# "write everything yourself."

def generic_agent_decision(ctx):
    spec = ctx.spec
    outputs = spec.get("outputs", {})
    per_agent_key = outputs.get("per_agent_key", "agents")
    field_map = outputs.get("fields")  # optional {response_key: record_key}; None copies every key
    prompt_fields_spec = spec.get("prompt", {}).get("fields", {})

    records = {}
    for agent_id in ctx.participants:
        fields = {
            field_name: _resolve_field(field_spec, ctx, agent_id)
            for field_name, field_spec in prompt_fields_spec.items()
        }
        response = ctx.agents.call(agent_id, **fields)
        records[agent_id] = _map_response(response, field_map)

    return {"round": ctx.round_number, "action": spec["name"], per_agent_key: records}


def _resolve_field(field_spec, ctx, agent_id):
    if "literal" in field_spec:
        return field_spec["literal"]
    source = field_spec.get("from")
    if source == "state":
        return _dotted_get(ctx.state, field_spec["path"])
    if source == "object":
        return ctx.objects.read(field_spec["object_id"], field_spec["field"], viewer_agent_id=agent_id)
    raise ValueError(f"unrecognized prompt field spec {field_spec!r}")


def _dotted_get(root, path):
    value = root
    for part in path.split("."):
        value = value[part]
    return value


def _map_response(response, field_map):
    if field_map is None:
        return dict(response)
    return {record_key: response.get(response_key) for response_key, record_key in field_map.items()}
