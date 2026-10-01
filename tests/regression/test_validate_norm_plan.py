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
    requirements = requirements if requirements is not None else [_role()]
    first_id = next((r.get("id") for r in requirements if r.get("id")), None)
    return {
        "requirements": requirements,
        "source_coverage": [{
            "source_clause": "the norm's only clause",
            "requirements": [first_id] if first_id else [],
            "coverage": "COVERED" if first_id else "AMBIGUOUS",
        }],
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


def _action(req_id="R2", actor=None, **overrides):
    req = {
        "id": req_id, "type": "ACTION", "description": "an action", "actor": actor,
        "agent_experience": {"knows": [], "decides": ["x"], "may_do": [], "may_not_do": [], "remembers": [], "observes": []},
    }
    req.update(overrides)
    return req


def test_actor_pointing_at_a_non_role_requirement_is_flagged():
    # The exact real defect (round 3, sim/run-20260930-224347): an
    # ACTION's "actor" pointed at R7 (a RULE requirement) instead of R10
    # (the actual Lake Keeper ROLE) -- presumably a copy/paste slip
    # during decomposition, undetected until a human read the plan by
    # hand. Nothing upstream of validate_norm_plan() catches a
    # requirement-id reference pointing at the wrong TYPE of requirement.
    rule = {
        "id": "R7", "type": "RULE", "description": "a deterministic rule", "attached_to": "R2",
        "agent_experience": {"knows": [], "decides": [], "may_do": [], "may_not_do": ["x"], "remembers": [], "observes": []},
    }
    role = _role("R10")
    action = _action("R6", actor="R7")  # should be "R10"
    errors = validate_norm_plan(_plan(requirements=[role, rule, action]))
    assert any("R6" in e and "actor" in e and "R7" in e and "ROLE" in e for e in errors)


def test_actor_pointing_at_the_correct_role_is_not_flagged():
    role = _role("R10")
    action = _action("R6", actor="R10")
    errors = validate_norm_plan(_plan(requirements=[role, action]))
    assert not any("actor" in e for e in errors)


def test_actor_naming_all_fishers_or_an_existing_role_is_not_flagged():
    errors = validate_norm_plan(_plan(requirements=[_action("R2", actor="all_fishers")]))
    assert not any("actor" in e for e in errors)
    errors = validate_norm_plan(_plan(requirements=[_action("R2", actor="fisher")]), known_roles={"fisher"})
    assert not any("actor" in e for e in errors)


def test_a_collective_or_undeclared_actor_is_flagged():
    # A real plan's guard-selection ACTION had actor "community" -- no
    # single agent this engine can prompt -- and the guard's own duty
    # ACTION had actor "lake_guard", free text instead of the ROLE
    # requirement's id. Both must be caught, not silently allowed.
    for actor in ("community", "lake_guard"):
        errors = validate_norm_plan(_plan(requirements=[_action("R4", actor=actor)]), known_roles={"fisher"})
        assert any("R4" in e and "actor" in e and actor in e for e in errors), actor


def test_rule_attached_to_a_non_action_requirement_is_flagged():
    role = _role("R1")
    rule = {
        "id": "R4", "type": "RULE", "description": "a rule", "attached_to": "R1",  # should name an ACTION
        "agent_experience": {"knows": [], "decides": [], "may_do": [], "may_not_do": ["x"], "remembers": [], "observes": []},
    }
    errors = validate_norm_plan(_plan(requirements=[role, rule]))
    assert any("R4" in e and "attached_to" in e and "R1" in e and "ACTION" in e for e in errors)


def test_rule_attached_to_the_correct_action_is_not_flagged():
    action = _action("R2", actor=None)
    rule = {
        "id": "R4", "type": "RULE", "description": "a rule", "attached_to": "R2",
        "agent_experience": {"knows": [], "decides": [], "may_do": [], "may_not_do": ["x"], "remembers": [], "observes": []},
    }
    errors = validate_norm_plan(_plan(requirements=[action, rule]))
    assert not any("attached_to" in e for e in errors)


def _with(req, **fields):
    return {**req, **fields}


def test_depends_on_naming_a_missing_id_or_itself_is_flagged():
    errors = validate_norm_plan(_plan(requirements=[_role("R1", depends_on=["R9"])]))
    assert any("R1" in e and "depends_on" in e and "R9" in e for e in errors)
    errors = validate_norm_plan(_plan(requirements=[_role("R1", depends_on=["R1"])]))
    assert any("R1" in e and "itself" in e for e in errors)


def test_a_depends_on_cycle_is_flagged():
    requirements = [_role("R1", depends_on=["R2"]), _role("R2", depends_on=["R3"]), _role("R3", depends_on=["R1"])]
    errors = validate_norm_plan(_plan(requirements=requirements))
    assert any("cycle" in e for e in errors)


def test_an_acyclic_dependency_chain_is_not_flagged():
    requirements = [_role("R1"), _role("R2", depends_on=["R1"]), _role("R3", depends_on=["R1", "R2"])]
    assert validate_norm_plan(_plan(requirements=requirements)) == []


def test_flow_steps_must_name_real_requirements():
    plan = _plan(requirements=[_role("R1")])
    plan["flows"] = [{"id": "F1", "steps": [
        {"requirement": "R1", "after": [], "next": ["R7"]},
        {"requirement": "R8", "after": ["R1"], "next": []},
    ]}]
    errors = validate_norm_plan(plan)
    assert any("F1" in e and "R7" in e for e in errors)
    assert any("F1" in e and "R8" in e for e in errors)


def test_source_coverage_is_required_and_reference_checked():
    plan = _plan()
    del plan["source_coverage"]
    assert any("source_coverage" in e for e in validate_norm_plan(plan))

    plan = _plan()
    plan["source_coverage"] = [
        {"source_clause": "a", "requirements": ["R1"], "coverage": "MOSTLY"},
        {"source_clause": "b", "requirements": [], "coverage": "COVERED"},
        {"source_clause": "c", "requirements": ["R42"], "coverage": "PARTIAL"},
        {"requirements": ["R1"], "coverage": "COVERED"},
    ]
    errors = validate_norm_plan(plan)
    assert any("source_coverage[0]" in e and "MOSTLY" in e for e in errors)
    assert any("source_coverage[1]" in e and "COVERED" in e for e in errors)
    assert any("source_coverage[2]" in e and "R42" in e for e in errors)
    assert any("source_coverage[3]" in e and "source_clause" in e for e in errors)


def test_an_agent_decision_needs_a_decision_context():
    bare = _action("R2", actor="all_fishers", judgment_required=True)
    errors = validate_norm_plan(_plan(requirements=[bare]))
    assert any("R2" in e and "decision_context" in e for e in errors)

    with_context = _with(bare, decision_context={"prompt_to": "every living fisher", "output": ["volunteer: bool"]})
    assert not any("decision_context" in e for e in validate_norm_plan(_plan(requirements=[with_context])))


def test_the_real_lake_guard_excerpt_is_rejected():
    # Verbatim shape of a real plan's R3/R4/R5 (guard role, selection,
    # inspection): selection collapsed into one ACTION by a collective
    # "community", the guard's duty attributed to free text "lake_guard"
    # instead of R3, and neither agent decision saying who is asked or
    # what comes back.
    exp = {"knows": ["x"], "decides": [], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
    requirements = [
        {"id": "R3", "type": "ROLE", "description": "Lake guard role exists, chosen by rotating draw from volunteers.",
         "exclusive": True, "clarity": "CLEAR", "agent_experience": exp},
        {"id": "R4", "type": "ACTION", "description": "Lake guard is chosen by rotating draw from volunteers.",
         "actor": "community", "judgment_required": True, "clarity": "CLEAR", "agent_experience": exp},
        {"id": "R5", "type": "ACTION", "description": "Lake guard checks daily logbook entries for limit compliance.",
         "actor": "lake_guard", "judgment_required": True, "clarity": "CLEAR", "agent_experience": exp},
    ]
    errors = validate_norm_plan(_plan(requirements=requirements), known_roles={"fisher"})
    assert any("R4" in e and "community" in e for e in errors)
    assert any("R5" in e and "lake_guard" in e for e in errors)
    assert any("R4" in e and "decision_context" in e for e in errors)
    assert any("R5" in e and "decision_context" in e for e in errors)


def test_the_architect_prompts_own_example_plan_passes_the_validator():
    # The JSON example in NORM_ARCHITECT_SYSTEM_PROMPT is what the model
    # imitates — if it ever stops passing the validator, every round
    # starts by being told its imitation of the example is wrong.
    import json
    import re

    from engine.llm_agents import NORM_ARCHITECT_SYSTEM_PROMPT

    example = re.findall(r"```json\s*\n(.*?)```", NORM_ARCHITECT_SYSTEM_PROMPT, re.DOTALL)[-1]
    plan = json.loads(example)
    plan["open_critiques"] = [{"requirement": "R4", "critique_question": "which rotation order?"}]
    assert validate_norm_plan(plan, known_roles={"fisher"}) == []
