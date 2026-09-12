# The zero-code execution path for a declarative ActionSpec (Level 2: "a
# new action assembled from existing generic components"). Deliberately
# small in scope — this covers "ask each eligible participating agent one
# question and record their answer" (optionally renaming response fields),
# with any rule attached to this action (state["config"]["rules"][name])
# automatically applied — eligibility (a rule can skip an agent's call
# entirely) and after_agent field patches both happen for free, the exact
# same way harvest's own hand-written loop applies them. The moment an
# action needs a role grant, an institutional fact, or a field computed by
# aggregating across other agents, it needs a small
# actions/handlers/{name}.py instead — that's Level 3/4, still far smaller
# than a full custom Action subclass used to be, never a cliff back to
# "write everything yourself."
#
# Uses engine.institution.agent_loop.per_agent_decision() for the actual
# per-agent loop — the same helper actions/handlers/{harvest,propose,
# vote}.py use — so this zero-code path and every hand-written handler
# get identical rule/eligibility semantics from one place.

from engine.institution.agent_loop import per_agent_decision


def generic_agent_decision(ctx):
    spec = ctx.spec
    outputs = spec.get("outputs", {})
    per_agent_key = outputs.get("per_agent_key", "agents")
    field_map = outputs.get("fields")  # optional {response_key: record_key}; None copies every key
    prompt_fields_spec = spec.get("prompt", {}).get("fields", {})

    def build_fields(agent_id):
        return {
            field_name: _resolve_field(field_spec, ctx, agent_id)
            for field_name, field_spec in prompt_fields_spec.items()
        }

    def build_record(agent_id, response):
        return _map_response(response, field_map)

    records = per_agent_decision(ctx, build_fields, build_record)
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
