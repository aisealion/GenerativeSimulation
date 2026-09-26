"""implement_and_evaluate_norm() (engine/simulate.py, 2026-09-27): compile-
class repairs and audit-class repairs now draw from separate budgets
(MAX_NORM_COMPILE_REPAIR_ATTEMPTS / MAX_NORM_AUDIT_REPAIR_ATTEMPTS)
instead of one shared pool — two real rounds (sim/run-20260926-204555)
showed a round needing several compile-fixes starving the harder audit-
refinement work of its own fair chance under a shared budget. These tests
exercise the counting/capping logic directly, with every real check
function and the architect/auditor calls monkeypatched out, since a real
round-trip would need opencode/Ollama."""
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
