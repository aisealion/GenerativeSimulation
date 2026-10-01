"""The per-requirement progress checkpoint and norm-engineer's own
attempt_log.json, after sim/run-20261001-160838 round 1 showed both
failing: norm-engineer's ten test functions were all `pass` stubs from its
first call, so every requirement read "Satisfied — do not touch" in all 13
repair messages (including while compile errors sat in two of those
requirements' own action specs); its attempt_log.json started with another
run's leftover history; and it deleted the log mid-round with `rm -f`."""
import json

import engine.simulate as simulate_module

STUB_SUITE = '''
"""Test suite for Round 1."""

def test_R1_role_creation():
    """Test that the role is created correctly."""
    # This is a structure test - just making sure the requirements are in place
    pass

def test_R3_action_creation():
    """Test that the action exists."""
    pass
'''


def _write(tmp_path, source, round_number=1):
    test_dir = tmp_path / "tests" / "norm_checks" / f"round_{round_number}"
    test_dir.mkdir(parents=True, exist_ok=True)
    path = test_dir / f"test_round_{round_number}.py"
    path.write_text(source)
    return path


# --- fix 1: an assertion-free test is not evidence -------------------------

def test_stub_tests_are_found_to_check_nothing(tmp_path):
    path = _write(tmp_path, STUB_SUITE)
    assert simulate_module._tests_without_assertions(path) == {"test_R1_role_creation", "test_R3_action_creation"}


def test_every_real_way_of_checking_counts(tmp_path):
    path = _write(tmp_path, '''
import pytest

def _check_ban(state):
    assert state["banned"]

def _via_helper(state):
    _check_ban(state)

def test_R1_plain_assert():
    assert 1 + 1 == 2

def test_R2_raises():
    with pytest.raises(ValueError):
        int("x")

def test_R3_mock_style(mock_call):
    mock_call.assert_called_once()

def test_R4_helper_that_asserts():
    _check_ban({"banned": True})

def test_R5_helper_of_a_helper():
    _via_helper({"banned": True})

def test_R6_runs_code_but_checks_nothing():
    result = sorted([3, 1, 2])
''')
    assert simulate_module._tests_without_assertions(path) == {"test_R6_runs_code_but_checks_nothing"}


def test_an_all_stub_suite_is_a_compile_class_error(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    _write(tmp_path, STUB_SUITE)
    [error] = simulate_module.norm_implementation_empty_tests_errors(1)
    assert "none of your 2 tests checks anything" in error
    assert "test_R1_role_creation" in error


def test_one_real_test_is_enough_to_pass_the_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    _write(tmp_path, STUB_SUITE + "\ndef test_R2_real():\n    assert True\n")
    assert simulate_module.norm_implementation_empty_tests_errors(1) == []
    assert simulate_module.norm_implementation_empty_tests_errors(2) == []  # no suite at all


def test_a_passing_stub_is_recorded_as_empty_and_never_counts_as_satisfied(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    _write(tmp_path, STUB_SUITE + "\ndef test_R2_real():\n    assert 2 > 1\n")
    plan = {"requirements": [{"id": "R1"}, {"id": "R2"}, {"id": "R3"}]}

    evidence = simulate_module._gather_norm_evidence(1, plan)

    assert any("EMPTY" in claim for claim in evidence["R1"])
    assert evidence["R2"] == ["acceptance test test_R2_real: PASS"]
    block = simulate_module._render_requirement_status_block(evidence)
    satisfied = next(line for line in block.splitlines() if line.startswith("Satisfied"))
    no_evidence = next(line for line in block.splitlines() if line.startswith("No test evidence"))
    assert "R2" in satisfied and "R1" not in satisfied and "R3" not in satisfied
    assert "R1" in no_evidence and "R3" in no_evidence


def test_self_reported_claims_alone_are_not_test_evidence():
    evidence = {"R1": ["registered role verifier in state/institution.json"]}
    block = simulate_module._render_requirement_status_block(evidence)
    assert "Satisfied" not in block
    assert "No test evidence" in block


# --- fix 2: nothing is "done — don't touch" while errors are open -----------

def test_a_requirement_whose_file_is_in_a_compile_error_is_not_done():
    evidence = {
        "R2": ["acceptance test test_R2_x: PASS"],
        "R3": ["acceptance test test_R3_x: PASS", "wrote state/actions/record_surplus.json"],
    }
    block = simulate_module._render_requirement_status_block(
        evidence, compile_errors=["state/actions/record_surplus.json: ValueError: boom"],
    )
    assert "Named in an error above — NOT done, even if their tests pass: R3" in block
    assert "Tests pass for: R2" in block
    assert "errors above take priority" in block
    assert "do not touch" not in block


def test_with_no_compile_errors_satisfied_still_means_preserve():
    block = simulate_module._render_requirement_status_block({"R2": ["acceptance test test_R2_x: PASS"]})
    assert "Satisfied — preserve these, do not touch their implementation or tests: R2" in block


# --- fix 3: each round starts with a clean tests/norm_checks/round_N/ -------

def test_leftovers_from_another_run_are_cleared_at_round_start(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    round_dir = tmp_path / "tests" / "norm_checks" / "round_1"
    round_dir.mkdir(parents=True)
    (round_dir / "attempt_log.json").write_text(json.dumps([{"attempt": 7, "approach": "another norm"}]))
    (round_dir / "test_round_1.py").write_text(STUB_SUITE)
    other_round = tmp_path / "tests" / "norm_checks" / "round_2"
    other_round.mkdir(parents=True)
    (other_round / "norm_plan.json").write_text("{}")

    simulate_module._clear_stale_round_checks(1)

    assert not round_dir.exists()
    assert (other_round / "norm_plan.json").exists()  # only this round's directory


def test_round_start_clears_before_the_architect_writes_its_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    stale = tmp_path / "tests" / "norm_checks" / "round_1" / "attempt_log.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("[]")
    seen_by_architect = []

    def _architect(round_number):
        seen_by_architect.append(stale.exists())
        return False, None

    monkeypatch.setattr(simulate_module, "run_norm_architect_with_retry", _architect)
    monkeypatch.setattr(simulate_module, "discard_norm_implementation", lambda round_number, errors: None)

    assert simulate_module.implement_and_evaluate_norm(1, {}) is False
    assert seen_by_architect == [False]


# --- fix 4: the harness restores a deleted or shrunk attempt log ------------

def _log(tmp_path):
    return tmp_path / "tests" / "norm_checks" / "round_1" / "attempt_log.json"


def test_a_normal_append_is_accepted_as_the_new_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    _log(tmp_path).parent.mkdir(parents=True)
    _log(tmp_path).write_text(json.dumps([{"attempt": 1}, {"attempt": 2}]))
    assert simulate_module._preserve_attempt_log(1, [{"attempt": 1}]) == [{"attempt": 1}, {"attempt": 2}]


def test_a_deleted_log_is_restored(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    saved = [{"attempt": 1}, {"attempt": 2}]
    assert simulate_module._preserve_attempt_log(1, saved) == saved
    assert json.loads(_log(tmp_path).read_text()) == saved


def test_a_wiped_log_keeps_its_history_and_the_new_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    _log(tmp_path).parent.mkdir(parents=True)
    _log(tmp_path).write_text(json.dumps([{"attempt": 3}]))  # rm -f, then wrote only its own entry
    restored = simulate_module._preserve_attempt_log(1, [{"attempt": 1}, {"attempt": 2}])
    assert restored == [{"attempt": 1}, {"attempt": 2}, {"attempt": 3}]
    assert json.loads(_log(tmp_path).read_text()) == restored


def test_a_corrupted_log_is_restored(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    _log(tmp_path).parent.mkdir(parents=True)
    _log(tmp_path).write_text('{"attempt": 4}')  # a bare object, not the array
    assert simulate_module._preserve_attempt_log(1, [{"attempt": 1}]) == [{"attempt": 1}]


def test_no_log_and_nothing_saved_creates_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    assert simulate_module._preserve_attempt_log(1, []) == []
    assert not _log(tmp_path).exists()
