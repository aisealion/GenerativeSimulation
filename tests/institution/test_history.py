from engine.institution.history import diff_institution

BASE = {
    "actions": {"harvest": {"spec": "state/actions/harvest.json", "protected": True}},
    "roles": {"fisher": {"exclusive": False, "introduced_round": 0}},
    "norm_types": {},
    "object_types": {},
    "state": {"community": ["stock_kg"]},
}


def test_no_changes_yields_empty_diff():
    assert diff_institution(BASE, BASE) == []


def test_added_action_is_detected():
    new = {**BASE, "actions": {**BASE["actions"], "report_catch": {"spec": "state/actions/report_catch.json"}}}
    changes = diff_institution(BASE, new)
    assert changes == [{"kind": "actions_added", "name": "report_catch",
                         "before": None, "after": {"spec": "state/actions/report_catch.json"}}]


def test_removed_norm_type_is_detected():
    old = {**BASE, "norm_types": {"trip_cap": {"description": "...", "owner": "norms/trip_cap.py"}}}
    changes = diff_institution(old, BASE)
    assert changes == [{"kind": "norm_types_removed", "name": "trip_cap",
                         "before": {"description": "...", "owner": "norms/trip_cap.py"}, "after": None}]


def test_changed_role_entry_is_detected():
    new = {**BASE, "roles": {"fisher": {"exclusive": False, "introduced_round": 0, "description": "added"}}}
    changes = diff_institution(BASE, new)
    assert len(changes) == 1
    assert changes[0]["kind"] == "roles_changed"
    assert changes[0]["name"] == "fisher"


def test_added_object_type_and_state_field_together():
    new = {
        **BASE,
        "object_types": {"communal_pool": {"description": "...", "owner": "state/object_types/communal_pool.json"}},
        "state": {"community": ["stock_kg", "reserve_kg"]},
    }
    changes = diff_institution(BASE, new)
    kinds = {c["kind"] for c in changes}
    assert kinds == {"object_types_added", "state_changed"}


def test_diff_is_order_independent_and_sorted_by_name():
    old = {**BASE, "roles": {"z_role": {}, "a_role": {}}}
    new = {**BASE, "roles": {}}
    changes = diff_institution(old, new)
    assert [c["name"] for c in changes] == ["a_role", "z_role"]
