import pytest

import engine.institution.rules as rules_module
from engine.institution.rules import Rule, RuleSet

ACTION = "_test_action"


class _FakeType(Rule):
    """A throwaway registered type for these tests — RuleSet.for_action()'s
    own mechanics (building instances, key resolution, duplicate
    detection) don't depend on which real actions/rules/*/*.py plugins
    happen to exist, and every action's own directory ships with none by
    default (see actions/rules/README.md), so these tests shouldn't
    depend on any either."""
    type_name = "_fake_type"


@pytest.fixture(autouse=True)
def _fake_rule_types(monkeypatch):
    monkeypatch.setattr(
        rules_module, "discover_rule_types",
        lambda action_name: {"_fake_type": _FakeType} if action_name == ACTION else {},
    )


def test_for_action_empty_config():
    assert RuleSet.for_action({}, ACTION).rules == []
    assert RuleSet.for_action({"rules": {ACTION: []}}, ACTION).rules == []


def test_for_action_builds_correct_instances():
    rules = RuleSet.for_action({"rules": {ACTION: [{"type": "_fake_type", "limit_kg": 12}]}}, ACTION).rules
    assert len(rules) == 1
    assert rules[0].type_name == "_fake_type"
    assert rules[0].key == "_fake_type"
    assert rules[0].params == {"type": "_fake_type", "limit_kg": 12}


def test_for_action_explicit_id():
    rules = RuleSet.for_action(
        {"rules": {ACTION: [{"type": "_fake_type", "id": "my_cap", "limit_kg": 12}]}}, ACTION,
    ).rules
    assert rules[0].key == "my_cap"


def test_for_action_unknown_type_raises():
    with pytest.raises(ValueError, match="unknown rule type"):
        RuleSet.for_action({"rules": {ACTION: [{"type": "nonexistent"}]}}, ACTION)


def test_for_action_duplicate_key_raises():
    with pytest.raises(ValueError, match="duplicate rule key"):
        RuleSet.for_action({"rules": {ACTION: [
            {"type": "_fake_type", "limit_kg": 12},
            {"type": "_fake_type", "limit_kg": 20},
        ]}}, ACTION)


def test_for_action_duplicate_type_ok_with_explicit_ids():
    rules = RuleSet.for_action({"rules": {ACTION: [
        {"type": "_fake_type", "id": "cap_a", "limit_kg": 12},
        {"type": "_fake_type", "id": "cap_b", "limit_kg": 20},
    ]}}, ACTION).rules
    assert [r.key for r in rules] == ["cap_a", "cap_b"]


def test_for_action_only_sees_rules_configured_for_its_own_action():
    """A rule configured for a different action must never leak into
    this action's own RuleSet — this is the actual point of organizing
    config by action instead of one flat list."""
    config = {"rules": {ACTION: [{"type": "_fake_type"}], "some_other_action": [{"type": "_fake_type"}]}}
    assert len(RuleSet.for_action(config, ACTION).rules) == 1
    # discover_rule_types is faked to return {} for any action other than
    # ACTION, so a rule "for" that other action can't even resolve here —
    # matching the real design, where each action only ever discovers its
    # own actions/rules/{action}/ directory.
    with pytest.raises(ValueError, match="unknown rule type"):
        RuleSet.for_action(config, "some_other_action")
