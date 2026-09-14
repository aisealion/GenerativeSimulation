import json
from pathlib import Path

def test_ledger_object_type_exists():

    obj = json.loads(Path("state/object_types/communal_ledger.json").read_text())
    assert obj["type_name"] == "communal_ledger"

def test_ledger_instance_exists():
    objs = json.loads(Path("state/objects.json").read_text())
    assert any(o["id"] == "communal_ledger" and o["type"] == "communal_ledger" for o in objs)
