import pytest

import engine.norms.registry as registry
from engine.norms.base import Norm
from engine.norms.registry import load_norms
from engine.norms.engine import NormEngine, tick_norm_lifecycles
from roles.roles import visible_facts


class _FakeType(Norm):
    type_name = "_fake_lifecycle_type"


@pytest.fixture(autouse=True)
def _fake_norm_types(monkeypatch):
    monkeypatch.setattr(registry, "NORM_TYPES", {"_fake_lifecycle_type": _FakeType})


def test_load_norms_without_round_number_ignores_lifecycle():
    config = {"norms": [
        {"type": "_fake_lifecycle_type", "lifecycle": {"active_from_round": 50}},
    ]}
    assert len(load_norms(config)) == 1


def test_load_norms_with_round_number_filters_out_not_yet_active():
    config = {"norms": [
        {"type": "_fake_lifecycle_type", "lifecycle": {"active_from_round": 50}},
    ]}
    assert load_norms(config, round_number=1) == []
    assert len(load_norms(config, round_number=50)) == 1


def test_load_norms_with_round_number_filters_out_expired():
    config = {"norms": [
        {"type": "_fake_lifecycle_type", "id": "temp",
         "lifecycle": {"active_from_round": 0, "duration_rounds": 5}},
    ]}
    assert len(load_norms(config, round_number=4)) == 1
    assert load_norms(config, round_number=5) == []


def test_load_norms_still_validates_an_inactive_entrys_type_and_duplicate_key():
    config = {"norms": [
        {"type": "nonexistent", "lifecycle": {"active_from_round": 999}},
    ]}
    with pytest.raises(ValueError, match="unknown norm type"):
        load_norms(config, round_number=1)


def test_norm_engine_from_config_forwards_round_number():
    config = {"norms": [
        {"type": "_fake_lifecycle_type", "lifecycle": {"active_from_round": 10}},
    ]}
    assert NormEngine.from_config(config, round_number=1).norms == []
    assert len(NormEngine.from_config(config, round_number=10).norms) == 1


def test_tick_norm_lifecycles_closes_norm_active_exactly_when_it_expires():
    config = {"norms": [
        {"type": "_fake_lifecycle_type", "lifecycle": {"active_from_round": 0, "duration_rounds": 3}},
    ]}
    fluents = []
    from roles.roles import set_fact
    set_fact(fluents, "norm_active", {"type": "_fake_lifecycle_type"}, "community", 0,
              narration="A rule is now in force.", visibility="public")

    tick_norm_lifecycles(config, fluents, round_number=1)
    tick_norm_lifecycles(config, fluents, round_number=2)
    assert visible_facts(fluents, "agent_0", 2)  # still open through round 2

    tick_norm_lifecycles(config, fluents, round_number=3)
    record = next(f for f in fluents if f["fluent"] == "norm_active")
    assert record["terminated_round"] == 3
    assert "expired" in record["end_narration"]

    # Ticking again on a later round must not double-close or re-narrate.
    fluents_before = list(fluents)
    tick_norm_lifecycles(config, fluents, round_number=4)
    assert fluents == fluents_before


def test_tick_norm_lifecycles_is_a_noop_for_norms_with_no_lifecycle():
    config = {"norms": [{"type": "_fake_lifecycle_type"}]}
    fluents = []
    tick_norm_lifecycles(config, fluents, round_number=5)
    assert fluents == []
