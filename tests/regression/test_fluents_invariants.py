import json
import pathlib

FLUENTS_PATH = pathlib.Path(__file__).resolve().parents[2] / "state" / "fluents.json"


def load_fluents():
    return json.loads(FLUENTS_PATH.read_text())


def test_exclusive_role_has_one_open_holder():
    fluents = load_fluents()
    open_by_role = {}
    for record in fluents:
        if record["terminated_round"] is not None:
            continue
        key = (record["fluent"], tuple(record["args"]))
        assert key not in open_by_role, (
            f"{key} has two open holder records: "
            f"{open_by_role[key]['holder']} and {record['holder']}"
        )
        open_by_role[key] = record


def test_narrated_facts_declare_visibility_and_event_type():
    fluents = load_fluents()
    for record in fluents:
        if record.get("narration"):
            assert record.get("visibility") in ("public", "agent_only"), (
                f"{record['fluent']}/{record['args']} has a narration but "
                f"visibility={record.get('visibility')!r} — must be "
                f"'public' or 'agent_only' or it can't be rendered"
            )
            assert record.get("event_type"), (
                f"{record['fluent']}/{record['args']} has a narration but no "
                f"event_type — it won't reach memory (mechanisms.roles.set_fact() "
                f"always sets one; a record missing it was written by hand)"
            )
        if record.get("end_narration"):
            assert record.get("end_visibility") in ("public", "agent_only"), (
                f"{record['fluent']}/{record['args']} has an end_narration but "
                f"end_visibility={record.get('end_visibility')!r} — must be "
                f"'public' or 'agent_only' or it can't be rendered"
            )
            assert record.get("end_event_type"), (
                f"{record['fluent']}/{record['args']} has an end_narration but no "
                f"end_event_type — it won't reach memory (mechanisms.roles.end_fact() "
                f"always sets one; a record missing it was written by hand)"
            )
