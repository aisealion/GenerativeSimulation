"""Locks in two things introduced by the norm-architect/norm-engineer/
norm-auditor split (2026-09-21):

1. The Self-Correction Gate (norm_implementation_failing_tests_errors()) —
   a pure-Python, no-LLM-call check that runs norm-architect's pre-written
   tests/norm_checks/round_{N}/ suite and feeds any failure's stack trace
   into the existing compile-repair loop (its own separate budget,
   MAX_NORM_COMPILE_REPAIR_ATTEMPTS, as of 2026-09-27).
2. The NORM_ENGINEER_CODE_PATHS fix to norm_implementation_no_code_changes_errors() —
   norm-architect writes tests/norm_checks/round_{N}/ BEFORE norm-engineer
   ever runs, so that directory is already dirty by the time this check
   executes; querying git status against the full NORM_ROUND_TRACKED_PATHS
   list (which includes tests/norm_checks) would let a norm-engineer that
   touched nothing at all slip past undetected.
"""
from types import SimpleNamespace

import engine.simulate as simulate_module


def _fake_completed_process(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_failing_tests_errors_returns_empty_when_round_directory_does_not_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)

    def _unexpected_run(*args, **kwargs):
        raise AssertionError("pytest should never be invoked when the round directory doesn't exist")

    monkeypatch.setattr(simulate_module.subprocess, "run", _unexpected_run)

    assert simulate_module.norm_implementation_failing_tests_errors(7) == []


def test_failing_tests_errors_returns_empty_when_suite_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "tests" / "norm_checks" / "round_7").mkdir(parents=True)
    monkeypatch.setattr(
        simulate_module.subprocess, "run",
        lambda *args, **kwargs: _fake_completed_process(returncode=0),
    )

    assert simulate_module.norm_implementation_failing_tests_errors(7) == []


def test_failing_tests_errors_surfaces_the_stack_trace_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "tests" / "norm_checks" / "round_7").mkdir(parents=True)
    monkeypatch.setattr(
        simulate_module.subprocess, "run",
        lambda *args, **kwargs: _fake_completed_process(
            returncode=1, stdout="FAKE_STACK_TRACE: AssertionError: expected a fine, got none",
        ),
    )

    errors = simulate_module.norm_implementation_failing_tests_errors(7)
    assert len(errors) == 1
    assert "round_7" in errors[0]
    assert "FAKE_STACK_TRACE" in errors[0]


def test_no_code_changes_check_excludes_norm_checks_from_the_git_status_query(monkeypatch):
    """The bug this guards against: querying the full NORM_ROUND_TRACKED_PATHS
    list (which includes tests/norm_checks) would always see norm-architect's
    own pre-existing tests as "something changed," even when norm-engineer
    itself touched nothing at all."""
    captured_paths = {}

    def _fake_run(cmd, **kwargs):
        # cmd == ["git", "status", "--porcelain", "--"] + <tracked paths>
        captured_paths["paths"] = cmd[4:]
        return _fake_completed_process(stdout="")  # nothing dirty in the queried paths

    monkeypatch.setattr(simulate_module.subprocess, "run", _fake_run)

    errors = simulate_module.norm_implementation_no_code_changes_errors()

    assert "tests/norm_checks" not in captured_paths["paths"]
    assert captured_paths["paths"] == simulate_module.NORM_ENGINEER_CODE_PATHS
    # With nothing dirty in the (correctly narrower) queried paths, this
    # must still report the zero-changes error rather than silently pass.
    assert len(errors) == 1
    assert "zero actual code" in errors[0]


def test_no_code_changes_check_passes_when_something_outside_norm_checks_changed(monkeypatch):
    monkeypatch.setattr(
        simulate_module.subprocess, "run",
        lambda cmd, **kwargs: _fake_completed_process(stdout=" M state/config.json\n"),
    )

    assert simulate_module.norm_implementation_no_code_changes_errors() == []
