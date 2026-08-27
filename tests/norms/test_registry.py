import pytest

from engine.norms.registry import NORM_TYPES, load_norms


def test_auto_discovery_finds_all_seed_types():
    # Subset, not equality: norm-implementer rounds legitimately add new
    # types over time (that's the whole point of auto-discovery) — this
    # only guards that the four seed types stay discoverable, not that
    # nothing else is ever added.
    assert {"catch_limit", "reserve", "violation_ban", "community_cap"} <= set(NORM_TYPES)


def test_load_norms_empty_config():
    assert load_norms({}) == []
    assert load_norms({"norms": []}) == []


def test_load_norms_builds_correct_instances():
    norms = load_norms({"norms": [{"type": "catch_limit", "limit_kg": 12}]})
    assert len(norms) == 1
    assert norms[0].type_name == "catch_limit"
    assert norms[0].key == "catch_limit"
    assert norms[0].params == {"type": "catch_limit", "limit_kg": 12}


def test_load_norms_explicit_id():
    norms = load_norms({"norms": [{"type": "catch_limit", "id": "my_cap", "limit_kg": 12}]})
    assert norms[0].key == "my_cap"


def test_load_norms_unknown_type_raises():
    with pytest.raises(ValueError, match="unknown norm type"):
        load_norms({"norms": [{"type": "nonexistent"}]})


def test_load_norms_duplicate_key_raises():
    with pytest.raises(ValueError, match="duplicate norm key"):
        load_norms({"norms": [
            {"type": "catch_limit", "limit_kg": 12},
            {"type": "catch_limit", "limit_kg": 20},
        ]})


def test_load_norms_duplicate_type_ok_with_explicit_ids():
    norms = load_norms({"norms": [
        {"type": "catch_limit", "id": "cap_a", "limit_kg": 12},
        {"type": "catch_limit", "id": "cap_b", "limit_kg": 20},
    ]})
    assert [n.key for n in norms] == ["cap_a", "cap_b"]
