import json

import engine.simulate as simulate_module


def _write_spec(root, round_number, verification_failures):
    spec_dir = root / "state" / "norm_specs"
    spec_dir.mkdir(parents=True, exist_ok=True)
    body = (
        "Requirement: R1\n"
        "Owner: actions/rules/harvest/example.py\n\n"
        "```json\n"
        + json.dumps({
            "classification": [{"requirement": "R1", "shape": "x", "level": 1,
                                 "owner": "actions/rules/harvest/example.py",
                                 "verification": "tests/norm_checks/test_r1.py"}],
            "verification_failures": verification_failures,
            "institution_json_updated": False,
        })
        + "\n```\n"
    )
    (spec_dir / f"round_{round_number}.md").write_text(body)


def test_no_errors_when_verification_failures_is_empty(tmp_path, monkeypatch):
    _write_spec(tmp_path, 1, [])
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    assert simulate_module.norm_implementation_unverified_requirements_errors(1) == []


def test_reports_named_failures_when_present(tmp_path, monkeypatch):
    _write_spec(tmp_path, 1, ["Enforce per-trip catch cap of 15 kg."])
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    errors = simulate_module.norm_implementation_unverified_requirements_errors(1)
    assert len(errors) == 1
    assert "Enforce per-trip catch cap of 15 kg." in errors[0]


def test_no_errors_when_spec_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    # No spec written at all — norm_implementation_missing_spec_errors()'s job, not this one's.
    assert simulate_module.norm_implementation_unverified_requirements_errors(1) == []


def test_no_errors_when_spec_predates_the_verification_failures_field(tmp_path, monkeypatch):
    spec_dir = tmp_path / "state" / "norm_specs"
    spec_dir.mkdir(parents=True)
    (spec_dir / "round_1.md").write_text(
        "Requirement: R1\n\n```json\n"
        + json.dumps({"classification": []})
        + "\n```\n"
    )
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    assert simulate_module.norm_implementation_unverified_requirements_errors(1) == []
