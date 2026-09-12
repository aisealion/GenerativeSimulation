import pytest

import engine.institution.rules as rules_module
from engine.institution.rules import Rule, RuleSet, tick_rule_lifecycles
from roles.roles import visible_facts, set_fact


class _FakeType(Rule):
    type_name = "_fake_lifecycle_type"


ACTION = "_test_action"


@pytest.fixture(autouse=True)
def _fake_rule_types(monkeypatch):
    monkeypatch.setattr(
        rules_module, "discover_rule_types",
        lambda action_name: {"_fake_lifecycle_type": _FakeType} if action_name == ACTION else {},
    )


def test_for_action_without_round_number_ignores_lifecycle():
    config = {"rules": {ACTION: [
        {"type": "_fake_lifecycle_type", "lifecycle": {"active_from_round": 50}},
    ]}}
    assert len(RuleSet.for_action(config, ACTION).rules) == 1


def test_for_action_with_round_number_filters_out_not_yet_active():
    config = {"rules": {ACTION: [
        {"type": "_fake_lifecycle_type", "lifecycle": {"active_from_round": 50}},
    ]}}
    assert RuleSet.for_action(config, ACTION, round_number=1).rules == []
    assert len(RuleSet.for_action(config, ACTION, round_number=50).rules) == 1


def test_for_action_with_round_number_filters_out_expired():
    config = {"rules": {ACTION: [
        {"type": "_fake_lifecycle_type", "id": "temp",
         "lifecycle": {"active_from_round": 0, "duration_rounds": 5}},
    ]}}
    assert len(RuleSet.for_action(config, ACTION, round_number=4).rules) == 1
    assert RuleSet.for_action(config, ACTION, round_number=5).rules == []


def test_for_action_still_validates_an_inactive_entrys_type_and_duplicate_key():
    config = {"rules": {ACTION: [
        {"type": "nonexistent", "lifecycle": {"active_from_round": 999}},
    ]}}
    with pytest.raises(ValueError, match="unknown rule type"):
        RuleSet.for_action(config, ACTION, round_number=1)


def test_tick_rule_lifecycles_closes_rule_active_exactly_when_it_expires():
    config = {"rules": {ACTION: [
        {"type": "_fake_lifecycle_type", "lifecycle": {"active_from_round": 0, "duration_rounds": 3}},
    ]}}
    fluents = []
    set_fact(fluents, "rule_active", {"action": ACTION, "type": "_fake_lifecycle_type"}, "community", 0,
              narration="A rule is now in force.", visibility="public")

    tick_rule_lifecycles(config, fluents, round_number=1)
    tick_rule_lifecycles(config, fluents, round_number=2)
    assert visible_facts(fluents, "agent_0", 2)  # still open through round 2

    tick_rule_lifecycles(config, fluents, round_number=3)
    record = next(f for f in fluents if f["fluent"] == "rule_active")
    assert record["terminated_round"] == 3
    assert "expired" in record["end_narration"]

    # Ticking again on a later round must not double-close or re-narrate.
    fluents_before = list(fluents)
    tick_rule_lifecycles(config, fluents, round_number=4)
    assert fluents == fluents_before


def test_tick_rule_lifecycles_is_a_noop_for_rules_with_no_lifecycle():
    config = {"rules": {ACTION: [{"type": "_fake_lifecycle_type"}]}}
    fluents = []
    tick_rule_lifecycles(config, fluents, round_number=5)
    assert fluents == []
