"""norm-architect reworked from a rich, implementation-flavored requirement
table + a raw Python test file into pure semantic compilation (2026-09-24,
by request): it classifies each requirement into ROLE/ACTION/OBJECT/RULE/
VISIBILITY/LIFECYCLE with an explicit agent_experience block, and writes
acceptance-test SPECIFICATIONS (given/when/expect), never Python — it has
no tools and no way to verify a file path or Python shape is correct, so
asking it to name one was asking it to guess at exactly the thing it's
least equipped to get right. norm-engineer (real repo access) now owns
translating those specs into runnable pytest as its own first step.

These tests replace the old python+json fixture pair with the new single
```json plan (requirements + acceptance_tests + open_critiques), and add
coverage for the new deterministic Harness Validator
(validate_norm_plan()) — which folds into the same second, finalizing
pass already used for critique resolution, rather than a separate retry
loop."""
import json

import engine.simulate as simulate_module


def _requirement(req_id="R1", req_type="ROLE", **overrides):
    req = {
        "id": req_id, "type": req_type, "description": f"{req_id} description",
        "clarity": "CLEAR", "clarity_critique": None, "clarity_resolution": None,
    }
    if req_type in simulate_module.NORM_PLAN_TYPES_REQUIRING_TESTS:
        req["agent_experience"] = {
            "knows": ["a fact"], "decides": [], "may_do": [], "may_not_do": [],
            "remembers": [], "observes": [],
        }
    req.update(overrides)
    return req


def _acceptance_test(req_id="R1", scenario="s1"):
    return {"requirement": req_id, "scenario": scenario, "given": {"x": 1}, "when": {"y": 2}, "expect": {"z": 3}}


def _valid_plan(requirements=None, acceptance_tests=None, open_critiques=None):
    if requirements is None:
        requirements = [_requirement()]
    if acceptance_tests is None:
        acceptance_tests = [
            _acceptance_test(r["id"]) for r in requirements
            if r["type"] in simulate_module.NORM_PLAN_TYPES_REQUIRING_TESTS
        ]
    return {
        "requirements": requirements,
        "acceptance_tests": acceptance_tests,
        "open_critiques": open_critiques or [],
    }


def _response(plan):
    return f"```json\n{json.dumps(plan)}\n```\n"


def test_writes_norm_plan_json_and_returns_it_on_a_clean_response(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    plan = _valid_plan()
    calls = []
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None, validator_errors=None: (
            calls.append((resolutions, validator_errors)) or _response(plan)
        ),
    )

    success, returned_plan = simulate_module.run_norm_architect(3)

    assert success is True
    assert returned_plan == plan
    assert calls == [(None, None)]  # no second, finalizing call — the plan was clean
    written = tmp_path / "tests" / "norm_checks" / "round_3" / "norm_plan.json"
    assert json.loads(written.read_text()) == plan


def test_returns_false_when_the_completion_call_itself_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None, validator_errors=None: None,
    )

    success, plan = simulate_module.run_norm_architect(3)

    assert success is False
    assert plan is None
    assert not (tmp_path / "tests").exists()


def test_returns_false_when_response_has_no_json_block(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None, validator_errors=None: "no fenced block at all",
    )

    success, plan = simulate_module.run_norm_architect(3)

    assert success is False
    assert plan is None


def test_returns_false_when_response_has_no_requirements_key(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None, validator_errors=None: (
            _response({"something_else": True})
        ),
    )

    success, plan = simulate_module.run_norm_architect(3)

    assert success is False
    assert plan is None


def test_resolves_open_critiques_and_uses_the_finalizing_pass_output(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")

    draft_plan = _valid_plan(open_critiques=[{"requirement": "R1", "critique_question": "what governs here?"}])
    final_plan = _valid_plan(requirements=[_requirement(description="R1 finalized")])
    pass_count = {"n": 0}

    def _fake_call(round_number, norm_text, context_bundle, resolutions=None, validator_errors=None):
        pass_count["n"] += 1
        if resolutions is None and validator_errors is None:
            return _response(draft_plan)
        assert resolutions == [{"critique_question": "what governs here?", "answer": "the later clause"}]
        assert validator_errors is None  # draft_plan is otherwise structurally valid
        return _response(final_plan)

    asked = []

    def _fake_ask(round_number, question):
        asked.append(question)
        return {"answer": "the later clause", "reasoning": "..."}

    monkeypatch.setattr(simulate_module, "call_norm_architect_agent", _fake_call)
    monkeypatch.setattr(simulate_module, "ask_norm_proposer", _fake_ask)

    success, returned_plan = simulate_module.run_norm_architect(7)

    assert success is True
    assert pass_count["n"] == 2
    assert asked == ["what governs here?"]
    assert returned_plan["requirements"][0]["description"] == "R1 finalized"


def test_caps_critique_resolution_at_the_shared_round_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    many_critiques = [{"requirement": "R1", "critique_question": f"question {i}?"} for i in range(8)]

    def _fake_call(round_number, norm_text, context_bundle, resolutions=None, validator_errors=None):
        if resolutions is None and validator_errors is None:
            return _response(_valid_plan(open_critiques=many_critiques))
        return _response(_valid_plan())

    asked = []
    monkeypatch.setattr(simulate_module, "call_norm_architect_agent", _fake_call)
    monkeypatch.setattr(
        simulate_module, "ask_norm_proposer",
        lambda round_number, question: (asked.append(question) or {"answer": "ok"}),
    )

    success, _ = simulate_module.run_norm_architect(1)

    assert success is True
    assert len(asked) == simulate_module.MAX_NORM_CLARIFICATIONS_PER_ROUND


def test_harness_validator_triggers_a_second_pass_and_fixes_are_applied(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")

    # A structurally invalid draft: an ACTION requirement missing its
    # required agent_experience block, and no open_critiques at all — the
    # validator, not the critique mechanism, must be what triggers the
    # second pass here.
    broken_requirement = {
        "id": "R2", "type": "ACTION", "description": "...", "actor": "R1",
        "clarity": "CLEAR", "clarity_critique": None, "clarity_resolution": None,
        # agent_experience deliberately omitted
    }
    draft_plan = {
        "requirements": [broken_requirement],
        "acceptance_tests": [_acceptance_test("R2")],
        "open_critiques": [],
    }
    fixed_plan = _valid_plan(requirements=[_requirement("R2", "ACTION")])
    pass_count = {"n": 0}

    def _fake_call(round_number, norm_text, context_bundle, resolutions=None, validator_errors=None):
        pass_count["n"] += 1
        if pass_count["n"] == 1:
            return _response(draft_plan)
        assert resolutions is None
        assert validator_errors and any("agent_experience" in e for e in validator_errors)
        return _response(fixed_plan)

    monkeypatch.setattr(simulate_module, "call_norm_architect_agent", _fake_call)

    success, returned_plan = simulate_module.run_norm_architect(2)

    assert success is True
    assert pass_count["n"] == 2
    assert returned_plan == fixed_plan


def test_returns_false_when_plan_is_still_invalid_after_the_finalizing_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")

    always_broken = {"requirements": [{"id": "R1", "type": "NOT_A_REAL_TYPE"}], "acceptance_tests": [], "open_critiques": []}
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None, validator_errors=None: _response(always_broken),
    )

    success, plan = simulate_module.run_norm_architect(4)

    assert success is False
    assert plan is None
    assert not (tmp_path / "tests" / "norm_checks" / "round_4" / "norm_plan.json").exists()


def test_run_norm_architect_with_retry_is_a_thin_passthrough(monkeypatch):
    monkeypatch.setattr(simulate_module, "run_norm_architect", lambda round_number: (True, {"requirements": []}))
    assert simulate_module.run_norm_architect_with_retry(9) == (True, {"requirements": []})
