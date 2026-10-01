"""implement_and_evaluate_norm() (engine/simulate.py, 2026-09-27): compile-
class repairs and audit-class repairs now draw from separate budgets
(MAX_NORM_COMPILE_REPAIR_ATTEMPTS / MAX_NORM_AUDIT_REPAIR_ATTEMPTS)
instead of one shared pool — two real rounds (sim/run-20260926-204555)
showed a round needing several compile-fixes starving the harder audit-
refinement work of its own fair chance under a shared budget. These tests
exercise the counting/capping logic directly, with every real check
function and the architect/auditor calls monkeypatched out, since a real
round-trip would need opencode/Ollama."""
import json

import engine.simulate as simulate_module


def _neutralize_checks(monkeypatch, compile_errors=None):
    """Stubs out every norm_implementation_*_errors() check
    implement_and_evaluate_norm() calls, so the test controls exactly
    what counts as a compile-class problem without touching the real
    filesystem/subprocess-based checks."""
    monkeypatch.setattr(simulate_module, "run_norm_architect_with_retry",
                         lambda round_number: (True, {"requirements": []}))
    monkeypatch.setattr(simulate_module, "norm_implementation_protected_path_violations", lambda: [])
    monkeypatch.setattr(simulate_module, "norm_implementation_compile_errors",
                         lambda: list(compile_errors) if compile_errors else [])
    monkeypatch.setattr(simulate_module, "norm_implementation_institution_errors", lambda: [])
    monkeypatch.setattr(simulate_module, "norm_implementation_orphaned_norm_errors", lambda: [])
    monkeypatch.setattr(simulate_module, "norm_implementation_missing_spec_errors", lambda round_number: [])
    monkeypatch.setattr(simulate_module, "norm_implementation_unverified_requirements_errors", lambda round_number: [])
    monkeypatch.setattr(simulate_module, "norm_implementation_no_code_changes_errors", lambda: [])
    monkeypatch.setattr(simulate_module, "norm_implementation_failing_tests_errors", lambda round_number: [])
    monkeypatch.setattr(simulate_module, "norm_implementation_runtime_errors", lambda: None)
    # Compile-repair now also gathers requirement evidence (see
    # test_compile_repair_message_lists_satisfied_and_unresolved_requirements
    # below) -- _gather_norm_evidence() runs a real pytest subprocess and
    # writes state/norm_evidence/round_{N}.json against the real ROOT
    # unless a test overrides this, so every other test here (which
    # doesn't care about evidence) must not touch the real filesystem.
    monkeypatch.setattr(simulate_module, "_gather_norm_evidence", lambda round_number, plan: {})
    # The round-start cleanup and the attempt-log restore both act on the
    # real ROOT's tests/norm_checks/ unless a test redirects them.
    monkeypatch.setattr(simulate_module, "_clear_stale_round_checks", lambda round_number: None)
    monkeypatch.setattr(simulate_module, "_preserve_attempt_log", lambda round_number, snapshot: snapshot)


def test_compile_repair_exhausts_its_own_budget_without_ever_reaching_the_auditor(monkeypatch):
    _neutralize_checks(monkeypatch, compile_errors=["persistent compile error"])
    monkeypatch.setattr(simulate_module, "run_norm_engineer_with_retry",
                         lambda round_number, extra_message=None, session_id=None: (True, "ses1"))

    audit_calls = []
    monkeypatch.setattr(simulate_module, "run_norm_auditor", lambda round_number: audit_calls.append(round_number))

    discards = []
    monkeypatch.setattr(simulate_module, "discard_norm_implementation",
                         lambda round_number, errors: discards.append((round_number, errors)))

    result = simulate_module.implement_and_evaluate_norm(1, {})

    assert result is False
    assert audit_calls == []  # never reached — compile errors never cleared
    assert len(discards) == 1
    assert discards[0][1] == ["persistent compile error"]


def test_audit_repair_exhausts_its_own_smaller_budget_after_compile_passes_immediately(monkeypatch):
    _neutralize_checks(monkeypatch, compile_errors=None)  # always clean
    engineer_calls = {"n": 0}

    def _fake_engineer(round_number, extra_message=None, session_id=None):
        engineer_calls["n"] += 1
        return True, "ses1"

    monkeypatch.setattr(simulate_module, "run_norm_engineer_with_retry", _fake_engineer)
    monkeypatch.setattr(simulate_module, "run_norm_auditor",
                         lambda round_number: {"result": "NEEDS_REPAIR", "text": "under-enforced"})

    discards = []
    monkeypatch.setattr(simulate_module, "discard_norm_implementation",
                         lambda round_number, errors: discards.append((round_number, errors)))

    result = simulate_module.implement_and_evaluate_norm(1, {})

    assert result is False
    assert len(discards) == 1
    assert str(simulate_module.MAX_NORM_AUDIT_REPAIR_ATTEMPTS) in discards[0][1][0]
    assert "audit-repair attempt(s)" in discards[0][1][0]
    # kickoff + MAX_NORM_AUDIT_REPAIR_ATTEMPTS repairs — tracked against
    # its own separate counter regardless of what MAX_NORM_COMPILE_REPAIR_
    # ATTEMPTS happens to be, since compile never failed once here.
    assert engineer_calls["n"] == 1 + simulate_module.MAX_NORM_AUDIT_REPAIR_ATTEMPTS


def test_compile_repair_message_lists_satisfied_and_unresolved_requirements(monkeypatch):
    # A real round needing 11 new actions was measuring its own progress
    # purely by attempt count -- nothing told a fresh compile-repair
    # attempt that most of them already existed and passed their own
    # tests, so it had no way to tell "9 of 11 done" from "nothing
    # works yet". This asserts the same requirement-status mechanism
    # audit-repair already gets (see the test below) is now also folded
    # into the compile-repair message.
    _neutralize_checks(monkeypatch, compile_errors=["persistent compile error"])
    monkeypatch.setattr(simulate_module, "run_norm_architect_with_retry",
                         lambda round_number: (True, {"requirements": [{"id": "R1"}, {"id": "R2"}]}))
    monkeypatch.setattr(simulate_module, "_gather_norm_evidence", lambda round_number, plan: {
        "R1": ["acceptance test test_R1_x: PASS"],
        "R2": [],
    })

    captured_messages = []

    def _fake_engineer(round_number, extra_message=None, session_id=None):
        captured_messages.append(extra_message)
        return True, "ses1"

    monkeypatch.setattr(simulate_module, "run_norm_engineer_with_retry", _fake_engineer)

    discards = []
    monkeypatch.setattr(simulate_module, "discard_norm_implementation",
                         lambda round_number, errors: discards.append((round_number, errors)))

    result = simulate_module.implement_and_evaluate_norm(1, {})

    assert result is False
    assert len(discards) == 1
    # captured_messages[0] is the kickoff call; [1] is the first
    # compile-repair message -- the one this test actually checks.
    assert len(captured_messages) >= 2
    message = captured_messages[1]
    # While compile errors are open, passing tests are reported as "tests
    # pass for", outranked by the errors — never "do not touch".
    assert "Tests pass for: R1" in message
    assert "errors above take priority" in message
    assert "Satisfied — preserve these" not in message
    assert "No test evidence at all" in message
    assert "R2" in message
    assert "don't rebuild a requirement whose tests already pass" in message


def test_audit_repair_message_lists_satisfied_and_unresolved_requirements(monkeypatch, tmp_path):
    _neutralize_checks(monkeypatch, compile_errors=None)
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    evidence_dir = tmp_path / "state" / "norm_evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "round_1.json").write_text(json.dumps({
        "R1": ["acceptance test test_R1_x: PASS"],
        "R2": ["acceptance test test_R2_x: FAIL — assert False"],
        "R3": [],
    }))

    captured_messages = []

    def _fake_engineer(round_number, extra_message=None, session_id=None):
        captured_messages.append(extra_message)
        return True, "ses1"

    monkeypatch.setattr(simulate_module, "run_norm_engineer_with_retry", _fake_engineer)

    verdicts = iter([
        {"result": "NEEDS_REPAIR", "text": "R2 is under-enforced."},
        {"result": "COMPLIANT", "text": "AUDIT_PASSED"},
    ])
    monkeypatch.setattr(simulate_module, "run_norm_auditor", lambda round_number: next(verdicts))
    monkeypatch.setattr(simulate_module, "record_institution_changes", lambda round_number: None)
    monkeypatch.setattr(simulate_module, "stage_norm_implementation", lambda round_number: True)

    result = simulate_module.implement_and_evaluate_norm(1, {})

    assert result is True
    # captured_messages[0] is the initial kickoff call — the repair message
    # (the one this test actually checks) is the one after it.
    assert len(captured_messages) == 2
    message = captured_messages[1]
    assert "Satisfied — preserve these" in message
    assert "R1" in message
    assert "No test evidence at all" in message
    assert "R3" in message
    # R2 is the one the auditor's report names, so it's reported as
    # auditor-flagged (outranking its own failing test), never "Satisfied".
    assert "Flagged by the auditor this round" in message
    assert "R2" in message.split("Flagged by the auditor this round")[1].split("\n")[0]


def test_repair_preamble_mentions_the_attempt_log_path_for_this_round():
    for repair_kind in ("compile", "audit"):
        message = simulate_module._render_engineer_repair_preamble(
            round_number=7, repair_kind=repair_kind, attempt=2, max_attempts=10,
            what_was_found="some problem", repair_history=[],
        )
        assert "tests/norm_checks/round_7/attempt_log.json" in message
        assert "Read" in message and "if it exists" in message
        assert "append" in message.lower()
        # The actual read-modify-write mechanics, not just the word
        # "append" — a real round used a single bare `write` each attempt
        # and silently erased its own prior entries every time.
        assert "read-modify-write" in message
        assert "parse it as a JSON array" in message
        assert "WHOLE updated array" in message or "WHOLE array" in message
        assert "never overwrite" in message.lower() or "never repeat" in message.lower()


def test_repair_preamble_always_tells_the_agent_to_review_the_whole_implementation():
    for repair_kind in ("compile", "audit"):
        message = simulate_module._render_engineer_repair_preamble(
            round_number=1, repair_kind=repair_kind, attempt=1, max_attempts=10,
            what_was_found="some problem", repair_history=[],
        )
        assert "ENTIRE implementation" in message
        assert "agent_experience" in message


def test_compliant_audit_stages_the_round_without_touching_either_repair_budget(monkeypatch):
    _neutralize_checks(monkeypatch, compile_errors=None)
    monkeypatch.setattr(simulate_module, "run_norm_engineer_with_retry",
                         lambda round_number, extra_message=None, session_id=None: (True, "ses1"))
    monkeypatch.setattr(simulate_module, "run_norm_auditor",
                         lambda round_number: {"result": "COMPLIANT", "text": "AUDIT_PASSED"})
    monkeypatch.setattr(simulate_module, "record_institution_changes", lambda round_number: None)
    monkeypatch.setattr(simulate_module, "stage_norm_implementation", lambda round_number: True)

    result = simulate_module.implement_and_evaluate_norm(1, {})

    assert result is True


def test_a_compile_regression_after_the_audit_started_draws_on_the_audit_budget(monkeypatch):
    # The exact shape of sim/run-20261001-160838 round 1: the compile
    # budget is fully spent reaching the auditor, then the audit repair
    # introduces one compile error. Before, that discarded the round on
    # the spot; now it's charged to the audit budget and gets fixed.
    _neutralize_checks(monkeypatch)
    monkeypatch.setattr(simulate_module, "MAX_NORM_COMPILE_REPAIR_ATTEMPTS", 1)
    compile_results = iter([["broken before audit"], [], ["regression from audit repair"], []])
    monkeypatch.setattr(simulate_module, "norm_implementation_compile_errors", lambda: next(compile_results))
    verdicts = iter([
        {"result": "NEEDS_REPAIR", "text": "AUDIT_FAILED: R1 is under-enforced."},
        {"result": "COMPLIANT", "text": "AUDIT_PASSED"},
    ])
    monkeypatch.setattr(simulate_module, "run_norm_auditor", lambda round_number: next(verdicts))
    messages = []
    monkeypatch.setattr(simulate_module, "run_norm_engineer_with_retry",
                         lambda round_number, extra_message=None, session_id=None: (messages.append(extra_message) or True, "ses1"))
    monkeypatch.setattr(simulate_module, "record_institution_changes", lambda round_number: None)
    monkeypatch.setattr(simulate_module, "stage_norm_implementation", lambda round_number: True)
    discards = []
    monkeypatch.setattr(simulate_module, "discard_norm_implementation",
                         lambda round_number, errors: discards.append(errors))

    result = simulate_module.implement_and_evaluate_norm(1, {})

    assert result is True
    assert discards == []
    # kickoff, compile repair 1, audit repair 1, then the regression's repair
    assert len(messages) == 4
    assert "regression from audit repair" in messages[3]


def test_no_repair_call_ever_reuses_a_previous_repair_calls_session(monkeypatch):
    # 2026-10-02: sim/run-20261001-211932 round 1 showed pairing (1&2
    # share a session, 3&4 a new one, ...) wasn't enough — one fresh
    # attempt alone produced 34 near-identical self-congratulatory text
    # turns, and its paired continuation then timed out after 3600s
    # having produced nothing. Every repair call must now be independently
    # fresh: session_id=None every time, regardless of attempt number or
    # repair kind, and nothing from one call's own discovered session_id
    # is ever threaded into the next.
    _neutralize_checks(monkeypatch, compile_errors=["persistent compile error"])
    session_ids_passed_in = []

    def _fake_engineer(round_number, extra_message=None, session_id=None):
        session_ids_passed_in.append(session_id)
        return True, f"discovered-session-{len(session_ids_passed_in)}"

    monkeypatch.setattr(simulate_module, "run_norm_engineer_with_retry", _fake_engineer)
    monkeypatch.setattr(simulate_module, "discard_norm_implementation", lambda round_number, errors: None)

    simulate_module.implement_and_evaluate_norm(1, {})

    # kickoff + 10 compile-repair attempts, every one of them session_id=None,
    # even though each _fake_engineer call "discovers" a new, real session id
    # that a pairing/threading bug would otherwise carry into the next call.
    assert len(session_ids_passed_in) == 1 + simulate_module.MAX_NORM_COMPILE_REPAIR_ATTEMPTS
    assert session_ids_passed_in == [None] * len(session_ids_passed_in)
