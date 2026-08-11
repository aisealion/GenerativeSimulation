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
