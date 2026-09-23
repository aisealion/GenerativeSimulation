"""_gather_norm_evidence() (engine/simulate.py, 2026-09-24) assembles the
structured per-requirement evidence package norm-auditor reviews instead
of a raw diff — see its own docstring. These tests run a real pytest
subprocess against a fabricated tests/norm_checks/round_N/ directory
(rather than monkeypatching subprocess.run) so the --junit-xml parsing
path is exercised for real, not just mocked."""
import json

from engine.simulate import _gather_norm_evidence


def _plan(requirement_ids, acceptance_tests=None):
    return {
        "requirements": [{"id": rid, "type": "RULE", "description": f"requirement {rid}"} for rid in requirement_ids],
        "acceptance_tests": acceptance_tests or [],
        "open_critiques": [],
    }


def test_missing_test_file_notes_no_acceptance_tests_for_every_requirement(tmp_path, monkeypatch):
    monkeypatch.setattr("engine.simulate.ROOT", tmp_path)
    plan = _plan(["R1", "R2"])

    evidence = _gather_norm_evidence(9, plan)

    assert any("no acceptance tests to run" in e for e in evidence["R1"])
    assert any("no acceptance tests to run" in e for e in evidence["R2"])
    written = json.loads((tmp_path / "state" / "norm_evidence" / "round_9.json").read_text())
    assert written == evidence


def test_passing_and_failing_acceptance_tests_are_recorded_per_requirement(tmp_path, monkeypatch):
    monkeypatch.setattr("engine.simulate.ROOT", tmp_path)
    round_dir = tmp_path / "tests" / "norm_checks" / "round_10"
    round_dir.mkdir(parents=True)
    (round_dir / "test_round_10.py").write_text(
        "def test_R1_over_quota():\n"
        "    assert True\n\n"
        "def test_R2_under_quota():\n"
        "    assert False, 'flat fine applied instead of threshold split'\n"
    )
    plan = _plan(["R1", "R2"])

    evidence = _gather_norm_evidence(10, plan)

    assert any("PASS" in e for e in evidence["R1"])
    assert any("FAIL" in e and "flat fine applied" in e for e in evidence["R2"])


def test_norm_finalizer_requirement_evidence_is_merged_in(tmp_path, monkeypatch):
    monkeypatch.setattr("engine.simulate.ROOT", tmp_path)
    specs_dir = tmp_path / "state" / "norm_specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "round_11.md").write_text(
        "### R1 — RULE\n\n"
        "```json\n"
        '{"requirement_evidence": {"R1": ["rule active in state/config.json"]}, '
        '"verification_failures": []}\n'
        "```\n"
    )
    plan = _plan(["R1"])

    evidence = _gather_norm_evidence(11, plan)

    assert "rule active in state/config.json" in evidence["R1"]


def test_self_grading_guardrail_flags_a_test_not_referencing_the_plans_literal_values(tmp_path, monkeypatch):
    monkeypatch.setattr("engine.simulate.ROOT", tmp_path)
    round_dir = tmp_path / "tests" / "norm_checks" / "round_12"
    round_dir.mkdir(parents=True)
    (round_dir / "test_round_12.py").write_text(
        "def test_R1_over_quota():\n"
        "    assert True\n"
    )
    plan = _plan(["R1"], acceptance_tests=[
        {
            "requirement": "R1", "scenario": "over_quota",
            "given": {"overage_pct": "15"}, "when": {}, "expect": {"fine": "5000"},
        }
    ])

    evidence = _gather_norm_evidence(12, plan)

    assert any("self-grading guardrail" in e for e in evidence["R1"])
