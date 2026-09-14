import json
import pathlib

def load_institution():
    path = pathlib.Path(__file__).resolve().parents[3] / "state" / "institution.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def test_tally_keeper_role_structural():
    institution = load_institution()
    roles = institution.get("roles", {})
    assert "tally_keeper" in roles, "tally_keeper role missing in institution.json"
    role = roles["tally_keeper"]
    # Check expected attributes
    assert role.get("exclusive") is True, "tally_keeper should be exclusive"
    assert role.get("description") == "rotating tally keeper for daily ledger", "description mismatch"
    assert role.get("introduced_round") == 2, "introduced_round should be 2"

# Functional aspects like daily rotation are not modelled in the simulation and thus not testable here.
