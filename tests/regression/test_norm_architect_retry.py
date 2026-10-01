"""norm-architect reworked from a rich, implementation-flavored requirement
table + a raw Python test file into pure semantic compilation (2026-09-24,
by request): it classifies each requirement into ROLE/ACTION/OBJECT/RULE/
VISIBILITY/LIFECYCLE with an explicit agent_experience block — it has no
tools and no way to verify a file path or Python shape is correct, so
asking it to name one was asking it to guess at exactly the thing it's
least equipped to get right.

2026-09-24 (same day, second change): norm-architect originally also
wrote acceptance-test SPECIFICATIONS (given/when/expect) for norm-engineer
to translate, with the Harness Validator requiring at least one per
ROLE/ACTION/RULE/VISIBILITY requirement. Dropped after a real run showed
this discarding whole rounds before norm-engineer ever started —
DeepSeek-R1 didn't reliably converge on covering every flagged gap even
across the validator's one bounded retry pass. norm-engineer now decides
scenarios itself from each requirement's agent_experience block and
writes the pytest — norm-architect's plan carries requirements only.

These tests cover the new deterministic Harness Validator
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
    if req_type in ("ROLE", "ACTION", "RULE", "VISIBILITY"):
        req["agent_experience"] = {
            "knows": ["a fact"], "decides": [], "may_do": [], "may_not_do": [],
            "remembers": [], "observes": [],
        }
    req.update(overrides)
    return req


def _valid_plan(requirements=None, open_critiques=None):
    if requirements is None:
        requirements = [_requirement()]
    return {
        "requirements": requirements,
        "source_coverage": [{
            "source_clause": "the norm's only clause",
            "requirements": [requirements[0]["id"]], "coverage": "COVERED",
        }],
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


def test_open_critiques_are_ignored_when_explicitly_disabled(tmp_path, monkeypatch):
    """NORM_ARCHITECT_CRITIQUES_ENABLED defaults to True (2026-09-29, the
    scoped-patch redesign) — this confirms the escape hatch still fully
    works when explicitly turned off: no ask_norm_proposer() call, no
    clarification call, the critiques just sit unresolved in the plan
    exactly as the first pass wrote them."""
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    monkeypatch.setattr(simulate_module, "NORM_ARCHITECT_CRITIQUES_ENABLED", False)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")

    plan = _valid_plan(open_critiques=[{"requirement": "R1", "critique_question": "what governs here?"}])
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None, validator_errors=None: _response(plan),
    )

    def _unexpected_ask(round_number, question):
        raise AssertionError("ask_norm_proposer() must never be called while critiques are disabled")

    def _unexpected_clarify(*args, **kwargs):
        raise AssertionError("clarification call must never happen while critiques are disabled")

    monkeypatch.setattr(simulate_module, "ask_norm_proposer", _unexpected_ask)
    monkeypatch.setattr(simulate_module, "call_norm_architect_clarification_agent", _unexpected_clarify)

    success, returned_plan = simulate_module.run_norm_architect(1)

    assert success is True
    assert returned_plan["open_critiques"] == plan["open_critiques"]  # left untouched
    assert "clarifications" not in returned_plan


def test_resolves_a_single_open_critique_with_a_scoped_patch(tmp_path, monkeypatch):
    """2026-09-29 redesign: critiques are enabled by default now, but the
    finalizing call is scoped to a patch, never "produce your final plan"
    — the exact failure mode that got this disabled on 2026-09-25 (a real
    round's finalizing pass re-deriving its whole plan from scratch,
    dropping requirements and restating critiques verbatim)."""
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    assert simulate_module.NORM_ARCHITECT_CRITIQUES_ENABLED is True  # the new default
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")

    r2 = _requirement("R2", "ROLE")
    draft_plan = _valid_plan(
        requirements=[_requirement("R1", "RULE"), r2],
        open_critiques=[{"requirement": "R1", "critique_question": "what governs here?"}],
    )
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None, validator_errors=None: _response(draft_plan),
    )

    asked = []
    monkeypatch.setattr(
        simulate_module, "ask_norm_proposer",
        lambda round_number, question: (asked.append(question) or {"answer": "the later clause"}),
    )

    patched_r1 = _requirement("R1", "RULE", description="R1 clarified", clarity_resolution="the later clause")
    clarify_calls = []

    def _fake_clarify(round_number, norm_text, context_bundle, plan, trigger_text):
        clarify_calls.append((plan, trigger_text))
        return _response({
            "clarification_for": "R1",
            "affected_requirements": ["R1"],
            "unchanged_requirements": ["R2"],
            "requirements": [patched_r1],
        })

    monkeypatch.setattr(simulate_module, "call_norm_architect_clarification_agent", _fake_clarify)

    success, returned_plan = simulate_module.run_norm_architect(7)

    assert success is True
    assert asked == ["what governs here?"]
    assert len(clarify_calls) == 1
    assert "what governs here?" in clarify_calls[0][1]
    assert "the later clause" in clarify_calls[0][1]

    by_id = {r["id"]: r for r in returned_plan["requirements"]}
    assert by_id["R1"]["description"] == "R1 clarified"
    # `r2` came back through a real JSON round-trip (call_norm_architect_agent's
    # mocked response is a JSON string, parsed fresh inside run_norm_architect),
    # so object identity can't survive that hop — content equality is the real
    # guarantee here; _apply_clarification_patch()'s own unit tests below check
    # actual object identity directly, where there's no serialization in between.
    assert by_id["R2"] == r2  # untouched
    assert returned_plan["clarifications"] == [{
        "clarification_for": "R1", "affected_requirements": ["R1"],
        "unchanged_requirements": ["R2"], "note": "critique on R1: what governs here?",
    }]


def test_caps_critique_resolution_at_the_shared_round_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    many_critiques = [{"requirement": "R1", "critique_question": f"question {i}?"} for i in range(8)]
    draft_plan = _valid_plan(open_critiques=many_critiques)

    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None, validator_errors=None: _response(draft_plan),
    )
    asked = []
    monkeypatch.setattr(
        simulate_module, "ask_norm_proposer",
        lambda round_number, question: (asked.append(question) or {"answer": "ok"}),
    )

    clarify_call_count = {"n": 0}

    def _fake_clarify(round_number, norm_text, context_bundle, plan, trigger_text):
        clarify_call_count["n"] += 1
        return _response({
            "affected_requirements": ["R1"], "unchanged_requirements": [],
            "requirements": [_requirement("R1")],
        })

    monkeypatch.setattr(simulate_module, "call_norm_architect_clarification_agent", _fake_clarify)

    success, _ = simulate_module.run_norm_architect(1)

    assert success is True
    assert len(asked) == simulate_module.MAX_NORM_CLARIFICATIONS_PER_ROUND
    assert clarify_call_count["n"] == simulate_module.MAX_NORM_CLARIFICATIONS_PER_ROUND


def test_harness_validator_triggers_a_clarification_patch_and_fixes_are_applied(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")

    # A structurally invalid draft: an ACTION requirement missing its
    # required agent_experience block, and no open_critiques at all — the
    # validator, not the critique mechanism, must be what triggers this.
    broken_requirement = {
        "id": "R2", "type": "ACTION", "description": "...", "actor": "R1",
        "clarity": "CLEAR", "clarity_critique": None, "clarity_resolution": None,
        # agent_experience deliberately omitted
    }
    r1 = _requirement("R1", "ROLE")
    draft_plan = {
        "requirements": [r1, broken_requirement],
        "source_coverage": [{"source_clause": "...", "requirements": ["R1", "R2"], "coverage": "COVERED"}],
        "open_critiques": [],
    }
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None, validator_errors=None: _response(draft_plan),
    )

    fixed_r2 = _requirement("R2", "ACTION", actor="R1")
    clarify_calls = []

    def _fake_clarify(round_number, norm_text, context_bundle, plan, trigger_text):
        clarify_calls.append(trigger_text)
        return _response({
            "affected_requirements": ["R2"], "unchanged_requirements": ["R1"],
            "requirements": [fixed_r2],
        })

    monkeypatch.setattr(simulate_module, "call_norm_architect_clarification_agent", _fake_clarify)

    success, returned_plan = simulate_module.run_norm_architect(2)

    assert success is True
    assert len(clarify_calls) == 1
    assert "agent_experience" in clarify_calls[0]
    by_id = {r["id"]: r for r in returned_plan["requirements"]}
    assert by_id["R1"] == r1  # untouched (content equality — see the identical
    # note on the sibling test above re: the JSON round-trip through the
    # mocked first-pass response breaking real object identity here)
    assert by_id["R2"]["agent_experience"]  # now present, structurally valid


def test_returns_false_when_plan_is_still_invalid_after_clarification(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")

    always_broken = {"requirements": [{"id": "R1", "type": "NOT_A_REAL_TYPE"}], "open_critiques": []}
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None, validator_errors=None: _response(always_broken),
    )
    # The clarification call itself fails outright — plan stays broken.
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_clarification_agent",
        lambda round_number, norm_text, context_bundle, plan, trigger_text: None,
    )

    success, plan = simulate_module.run_norm_architect(4)

    assert success is False
    assert plan is None
    assert not (tmp_path / "tests" / "norm_checks" / "round_4" / "norm_plan.json").exists()


def test_apply_clarification_patch_rejects_a_patch_that_drops_an_id():
    plan = _valid_plan(requirements=[_requirement("R1"), _requirement("R2", "ROLE")])
    patch_text = _response({
        "affected_requirements": ["R1"],
        "unchanged_requirements": [],  # R2 missing entirely
        "requirements": [_requirement("R1", description="patched")],
    })
    merged, reason = simulate_module._apply_clarification_patch(plan, patch_text, note="test")
    assert merged is None
    assert "R2" in reason


def test_apply_clarification_patch_rejects_a_patch_that_invents_an_id():
    plan = _valid_plan(requirements=[_requirement("R1")])
    patch_text = _response({
        "affected_requirements": ["R1"],
        "unchanged_requirements": ["R99"],  # doesn't exist in the plan
        "requirements": [_requirement("R1", description="patched")],
    })
    merged, reason = simulate_module._apply_clarification_patch(plan, patch_text, note="test")
    assert merged is None
    assert "R99" in reason


def test_apply_clarification_patch_rejects_overlapping_affected_and_unchanged_sets():
    plan = _valid_plan(requirements=[_requirement("R1"), _requirement("R2", "ROLE")])
    patch_text = _response({
        "affected_requirements": ["R1"],
        "unchanged_requirements": ["R1", "R2"],  # R1 claimed both ways
        "requirements": [_requirement("R1", description="patched")],
    })
    merged, reason = simulate_module._apply_clarification_patch(plan, patch_text, note="test")
    assert merged is None
    assert "R1" in reason


def test_apply_clarification_patch_rejects_an_edit_to_an_id_not_declared_affected():
    """The exact 2026-09-25 regression this redesign closes: a patch
    editing something it didn't declare as affected is rejected wholesale
    — a real, honest patch or nothing, never a partial one the harness
    has to guess about."""
    plan = _valid_plan(requirements=[_requirement("R1"), _requirement("R2", "ROLE", description="original")])
    patch_text = _response({
        "affected_requirements": ["R1"],
        "unchanged_requirements": ["R2"],
        "requirements": [
            _requirement("R1", description="patched"),
            _requirement("R2", "ROLE", description="sneakily rewritten too"),
        ],
    })
    merged, reason = simulate_module._apply_clarification_patch(plan, patch_text, note="test")
    assert merged is None


def test_apply_clarification_patch_merges_cleanly_on_a_well_formed_patch():
    r2 = _requirement("R2", "ROLE")
    plan = _valid_plan(requirements=[_requirement("R1"), r2])
    patched_r1 = _requirement("R1", description="patched")
    patch_text = _response({
        "clarification_for": "R1",
        "affected_requirements": ["R1"],
        "unchanged_requirements": ["R2"],
        "requirements": [patched_r1],
    })

    merged, reason = simulate_module._apply_clarification_patch(plan, patch_text, note="test note")

    assert reason is None
    by_id = {r["id"]: r for r in merged["requirements"]}
    assert by_id["R1"]["description"] == "patched"
    assert by_id["R2"] is r2
    assert merged["clarifications"] == [{
        "clarification_for": "R1", "affected_requirements": ["R1"],
        "unchanged_requirements": ["R2"], "note": "test note",
    }]


def test_run_norm_architect_with_retry_is_a_thin_passthrough(monkeypatch):
    monkeypatch.setattr(simulate_module, "run_norm_architect", lambda round_number: (True, {"requirements": []}))
    assert simulate_module.run_norm_architect_with_retry(9) == (True, {"requirements": []})


def test_apply_clarification_patch_can_add_a_new_requirement_and_replace_coverage():
    # A coverage gap (a clause nothing implements) can only be fixed by
    # ADDING a requirement — existing ids still only change through
    # affected_requirements, exactly as before.
    r1 = _requirement("R1")
    plan = _valid_plan(requirements=[r1])
    new_r2 = _requirement("R2", "ACTION", actor="R1")
    new_coverage = [{"source_clause": "clause", "requirements": ["R1", "R2"], "coverage": "COVERED"}]
    new_flows = [{"id": "F1", "steps": [{"requirement": "R2", "after": [], "next": []}]}]
    patch_text = _response({
        "affected_requirements": [], "unchanged_requirements": ["R1"], "added_requirements": ["R2"],
        "requirements": [new_r2], "source_coverage": new_coverage, "flows": new_flows,
    })

    merged, reason = simulate_module._apply_clarification_patch(plan, patch_text, note="coverage gap")

    assert reason is None
    assert [r["id"] for r in merged["requirements"]] == ["R1", "R2"]
    assert merged["requirements"][0] is r1
    assert merged["source_coverage"] == new_coverage
    assert merged["flows"] == new_flows
    assert merged["clarifications"][-1]["added_requirements"] == ["R2"]
    assert merged["clarifications"][-1]["replaced"] == ["flows", "source_coverage"]


def test_apply_clarification_patch_rejects_an_added_id_that_already_exists():
    plan = _valid_plan(requirements=[_requirement("R1")])
    patch_text = _response({
        "affected_requirements": [], "unchanged_requirements": ["R1"], "added_requirements": ["R1"],
        "requirements": [_requirement("R1", description="sneaky overwrite")],
    })
    merged, reason = simulate_module._apply_clarification_patch(plan, patch_text, note="test")
    assert merged is None
    assert "R1" in reason


def test_apply_clarification_patch_rejects_an_undeclared_new_requirement():
    plan = _valid_plan(requirements=[_requirement("R1")])
    patch_text = _response({
        "affected_requirements": [], "unchanged_requirements": ["R1"],
        "requirements": [_requirement("R2", "ROLE")],  # R2 never declared as added
    })
    merged, reason = simulate_module._apply_clarification_patch(plan, patch_text, note="test")
    assert merged is None


def test_mas_summary_lists_actions_in_round_order_with_participants(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "state" / "actions").mkdir(parents=True)
    (tmp_path / "state" / "config.json").write_text(json.dumps({"agent_count": 5, "rules": {"harvest": [{"type": "cap"}]}}))
    (tmp_path / "state" / "institution.json").write_text(json.dumps({
        "actions": {"harvest": {}, "inspect": {}},
        "roles": {"fisher": {"exclusive": False, "description": "a fisher"}},
        "state": {"fisher": ["effort"], "community": ["stock_kg"]},
    }))
    (tmp_path / "state" / "actions" / "harvest.json").write_text(json.dumps({
        "name": "harvest", "description": "fish", "scheduling": {"gate": "true", "after": None, "before": None},
        "participation": {"policy": "all_alive_fishers"},
    }))
    (tmp_path / "state" / "actions" / "inspect.json").write_text(json.dumps({
        "name": "inspect", "description": "guard inspects", "scheduling": {"gate": "true", "after": "harvest", "before": None},
        "participation": {"policy": "role_holders", "role": "guard"},
    }))

    summary = simulate_module._mas_summary()

    assert [step["action"] for step in summary["round_sequence"]] == ["harvest", "inspect"]
    assert summary["round_sequence"][1]["who_decides"] == "whoever currently holds the 'guard' role, each deciding separately"
    assert summary["round_sequence"][0]["who_decides"] == "every living fisherman, each deciding separately"
    assert summary["roles"] == {"fisher": {"exclusive": False, "description": "a fisher"}}
    assert "cap" in summary["rules_fishermen_are_automatically_bound_by"]["harvest"][0]
    assert "not something they choose" in summary["rules_fishermen_are_automatically_bound_by"]["harvest"][0]
    assert summary["agents"]["count"] == 5
    assert "multi-agent system" in summary["multi_agent_note"]
    assert "5" in summary["multi_agent_note"]
    assert summary["capabilities"]


def test_a_second_structural_fix_pass_gets_a_chance_when_the_first_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    draft_plan = {"requirements": [_requirement("R1")], "open_critiques": []}  # no source_coverage
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None, validator_errors=None: _response(draft_plan),
    )
    responses = iter([
        None,  # first structural-fix call fails outright
        _response({
            "affected_requirements": [], "unchanged_requirements": ["R1"],
            "requirements": [],
            "source_coverage": [{"source_clause": "x", "requirements": ["R1"], "coverage": "COVERED"}],
        }),
    ])
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_clarification_agent",
        lambda round_number, norm_text, context_bundle, plan, trigger_text: next(responses),
    )

    success, plan = simulate_module.run_norm_architect(5)

    assert success is True
    assert plan["source_coverage"][0]["requirements"] == ["R1"]


# --- tolerant JSON parsing + one retry on an unusable plan -------------------
# sim/run-20261001-202621 round 1 was discarded before norm-engineer ever ran:
# the architect annotated its plan with three `// ...` comments, strict
# json.loads() failed, and the round ended. With the comments removed the plan
# had zero validator errors.

def test_lenient_json_drops_comments_and_trailing_commas_but_not_string_content():
    text = '''{
      "attached_to": "harvest",  // Attach to existing harvest action
      /* a block comment */
      "url": "https://example.org/a//b",
      "quote": "he said \\"// not a comment\\" and left, ]",
      "list": [1, 2, 3,],
      "nested": {"x": true,},
    }'''
    parsed = simulate_module._loads_llm_json(text)
    assert parsed == {
        "attached_to": "harvest",
        "url": "https://example.org/a//b",
        "quote": 'he said "// not a comment" and left, ]',
        "list": [1, 2, 3],
        "nested": {"x": True},
    }


def test_strict_json_is_parsed_unchanged_and_hopeless_text_still_raises():
    assert simulate_module._loads_llm_json('{"a": "x // y"}') == {"a": "x // y"}
    try:
        simulate_module._loads_llm_json("{requirements: [}")
        raise AssertionError("expected a JSONDecodeError")
    except json.JSONDecodeError:
        pass


def test_a_plan_with_comments_is_used_without_any_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    # Multi-line, as the model actually writes it — a "//" comment runs to
    # the end of its own line only.
    commented = "```json\n" + json.dumps(_valid_plan(), indent=2).replace(
        '"type": "ROLE",', '"type": "ROLE",  // the role itself'
    ) + "\n```\n"
    assert "// the role itself" in commented
    calls = []
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None, validator_errors=None: (
            calls.append(validator_errors) or commented
        ),
    )

    success, plan = simulate_module.run_norm_architect(1)

    assert success is True
    assert calls == [None]
    assert plan["requirements"][0]["type"] == "ROLE"


def test_an_unusable_plan_gets_one_retry_quoting_the_problem(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    responses = iter(["```json\n{requirements: [oops}\n```", _response(_valid_plan())])
    calls = []
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None, validator_errors=None: (
            calls.append(validator_errors) or next(responses)
        ),
    )

    success, plan = simulate_module.run_norm_architect(1)

    assert success is True
    assert len(calls) == 2 and calls[0] is None
    assert "isn't valid JSON" in calls[1][0] and "no // or /* */ comments" in calls[1][0]


def test_apply_clarification_patch_accepts_an_omitted_requirements_key_when_nothing_is_affected():
    # sim/run-20261002-105239 round 1: a patch that only needed to replace
    # source_coverage correctly set affected_requirements to [] and every
    # existing id into unchanged_requirements, but omitted "requirements"
    # entirely (nothing of any requirement's own content was changing) --
    # the strict isinstance(..., list) check rejected the whole,
    # otherwise-correct patch over that one missing key.
    r1, r2 = _requirement("R1"), _requirement("R2", "ROLE")
    plan = _valid_plan(requirements=[r1, r2])
    new_coverage = [{"source_clause": "x", "requirements": ["R1"], "coverage": "COVERED", "note": None}]
    patch_text = _response({
        "affected_requirements": [],
        "unchanged_requirements": ["R1", "R2"],
        "source_coverage": new_coverage,
        # no "requirements" key at all
    })

    merged, reason = simulate_module._apply_clarification_patch(plan, patch_text, note="test")

    assert reason is None
    assert merged["requirements"] == [r1, r2]  # untouched, same objects
    assert merged["source_coverage"] == new_coverage


def test_apply_clarification_patch_still_rejects_a_genuinely_malformed_key():
    # A key that's PRESENT but the wrong type is still a real error --
    # only an ABSENT key defaults to empty.
    plan = _valid_plan(requirements=[_requirement("R1")])
    patch_text = _response({
        "affected_requirements": "R1",  # should be a list, not a bare string
        "unchanged_requirements": [],
        "requirements": [_requirement("R1", description="patched")],
    })
    merged, reason = simulate_module._apply_clarification_patch(plan, patch_text, note="test")
    assert merged is None
    assert "must be lists" in reason


def test_apply_clarification_patch_accepts_a_missing_unchanged_requirements_key_too():
    r1 = _requirement("R1")
    plan = _valid_plan(requirements=[r1])
    patched_r1 = _requirement("R1", description="patched")
    patch_text = _response({
        "affected_requirements": ["R1"],
        "requirements": [patched_r1],
        # no "unchanged_requirements" key -- fine, there's nothing left unchanged
    })
    merged, reason = simulate_module._apply_clarification_patch(plan, patch_text, note="test")
    assert reason is None
    assert merged["requirements"][0]["description"] == "patched"
