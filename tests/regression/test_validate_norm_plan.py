"""Direct unit tests for validate_norm_plan() — the deterministic Harness
Validator (2026-09-24) that sits between norm-architect and norm-engineer,
catching structural incompleteness before an expensive opencode session
ever starts. Pure Python, no LLM call, no monkeypatching needed.

2026-09-24 (same day, second change): norm-architect no longer proposes
acceptance tests at all — a real run showed the validator's old
"every ROLE/ACTION/RULE/VISIBILITY needs >=1 acceptance_tests entry" rule
discarding whole rounds (see rounds 1 and 2 of sim/run-20260924-005713)
because DeepSeek-R1 didn't reliably converge on covering every flagged
gap even across the one bounded retry pass. norm-engineer now decides
scenarios itself, so the plan carries no acceptance_tests at all any
more, and this file's tests for that rule are removed accordingly."""
from engine.simulate import validate_norm_plan


def _role(req_id="R1", **overrides):
    req = {
        "id": req_id, "type": "ROLE", "description": "a role",
        "agent_experience": {"knows": ["x"], "decides": [], "may_do": [], "may_not_do": [], "remembers": [], "observes": []},
    }
    req.update(overrides)
    return req


def _plan(requirements=None, open_critiques=None):
    return {
        "requirements": requirements if requirements is not None else [_role()],
        "open_critiques": open_critiques or [],
    }


def test_a_well_formed_minimal_plan_is_valid():
    assert validate_norm_plan(_plan()) == []


def test_empty_requirements_list_is_invalid():
    errors = validate_norm_plan({"requirements": [], "open_critiques": []})
    assert errors
    assert any("non-empty" in e for e in errors)


def test_missing_requirements_key_is_invalid():
    errors = validate_norm_plan({"open_critiques": []})
    assert errors


def test_requirement_with_no_id_is_flagged():
    errors = validate_norm_plan(_plan(requirements=[{"type": "OBJECT", "description": "x"}]))
    assert any("no \"id\"" in e for e in errors)


def test_duplicate_ids_are_flagged():
    errors = validate_norm_plan(_plan(requirements=[_role("R1"), _role("R1")]))
    assert any("duplicate id" in e for e in errors)


def test_unknown_type_is_flagged():
    errors = validate_norm_plan(_plan(requirements=[{"id": "R1", "type": "PLACE", "description": "x"}]))
    assert any("must be one of" in e for e in errors)


def test_unresolved_type_requires_a_reason():
    errors = validate_norm_plan(_plan(requirements=[{"id": "R1", "type": "UNRESOLVED"}]))
    assert any("UNRESOLVED" in e and "reason" in e for e in errors)

    ok = validate_norm_plan(_plan(
        requirements=[{"id": "R1", "type": "UNRESOLVED", "reason": "nothing in the norm fits"}],
    ))
    assert ok == []


def test_missing_description_is_flagged():
    req = _role()
    del req["description"]
    errors = validate_norm_plan(_plan(requirements=[req]))
    assert any("description" in e for e in errors)


def test_role_action_rule_visibility_require_agent_experience():
    for req_type in ("ROLE", "ACTION", "RULE", "VISIBILITY"):
        req = {"id": "R1", "type": req_type, "description": "x"}
        errors = validate_norm_plan(_plan(requirements=[req]))
        assert any("agent_experience" in e for e in errors), f"{req_type} should require agent_experience"


def test_object_and_lifecycle_do_not_require_agent_experience():
    for req_type in ("OBJECT", "LIFECYCLE"):
        req = {"id": "R1", "type": req_type, "description": "x"}
        errors = validate_norm_plan(_plan(requirements=[req]))
        assert not any("agent_experience" in e for e in errors), f"{req_type} shouldn't require agent_experience"


def test_open_critique_referencing_unknown_requirement_is_flagged():
    errors = validate_norm_plan(_plan(open_critiques=[{"requirement": "R99", "critique_question": "?"}]))
    assert any("R99" in e for e in errors)


def test_open_critique_missing_question_is_flagged():
    errors = validate_norm_plan(_plan(open_critiques=[{"requirement": "R1"}]))
    assert any("critique_question" in e for e in errors)
