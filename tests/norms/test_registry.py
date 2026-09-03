import pytest

import engine.norms.registry as registry
from engine.norms.base import Norm
from engine.norms.registry import load_norms


class _FakeType(Norm):
    """A throwaway registered type for these tests — load_norms()'s own
    mechanics (building instances, key resolution, duplicate detection)
    don't depend on which real norms/*.py plugins happen to exist, and
    norms/ ships with none by default (see norms/README.md), so these
    tests shouldn't depend on any either."""
    type_name = "_fake_type"


@pytest.fixture(autouse=True)
def _fake_norm_types(monkeypatch):
    monkeypatch.setattr(registry, "NORM_TYPES", {"_fake_type": _FakeType})


def test_load_norms_empty_config():
    assert load_norms({}) == []
    assert load_norms({"norms": []}) == []


def test_load_norms_builds_correct_instances():
    norms = load_norms({"norms": [{"type": "_fake_type", "limit_kg": 12}]})
    assert len(norms) == 1
    assert norms[0].type_name == "_fake_type"
    assert norms[0].key == "_fake_type"
    assert norms[0].params == {"type": "_fake_type", "limit_kg": 12}


def test_load_norms_explicit_id():
    norms = load_norms({"norms": [{"type": "_fake_type", "id": "my_cap", "limit_kg": 12}]})
    assert norms[0].key == "my_cap"


def test_load_norms_unknown_type_raises():
    with pytest.raises(ValueError, match="unknown norm type"):
        load_norms({"norms": [{"type": "nonexistent"}]})


def test_load_norms_duplicate_key_raises():
    with pytest.raises(ValueError, match="duplicate norm key"):
        load_norms({"norms": [
            {"type": "_fake_type", "limit_kg": 12},
            {"type": "_fake_type", "limit_kg": 20},
        ]})


def test_load_norms_duplicate_type_ok_with_explicit_ids():
    norms = load_norms({"norms": [
        {"type": "_fake_type", "id": "cap_a", "limit_kg": 12},
        {"type": "_fake_type", "id": "cap_b", "limit_kg": 20},
    ]})
    assert [n.key for n in norms] == ["cap_a", "cap_b"]
