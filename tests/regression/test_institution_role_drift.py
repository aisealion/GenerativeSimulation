import json

import engine.simulate as simulate_module


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _setup(tmp_path, monkeypatch, roles):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    _write(tmp_path / "state" / "institution.json", json.dumps({"actions": {}, "object_types": {}, "roles": roles}))


def test_a_registered_role_with_a_matching_directive_file_is_clean(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, {"fisher": {}})
    _write(tmp_path / "prompts" / "role_directives" / "fisher.md", "Fisher text.")

    assert simulate_module.norm_implementation_institution_errors() == []


def test_a_registered_role_with_no_directive_file_is_flagged(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, {"fisher": {}, "recorder": {}})
    _write(tmp_path / "prompts" / "role_directives" / "fisher.md", "Fisher text.")
    # recorder.md deliberately not written.

    errors = simulate_module.norm_implementation_institution_errors()
    assert len(errors) == 1
    assert "recorder" in errors[0]
    assert "role_directives" in errors[0]


def test_clearing_the_gap_makes_the_check_clean_again(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, {"fisher": {}, "recorder": {}})
    _write(tmp_path / "prompts" / "role_directives" / "fisher.md", "Fisher text.")

    assert simulate_module.norm_implementation_institution_errors() != []

    _write(tmp_path / "prompts" / "role_directives" / "recorder.md", "Recorder text.")
    assert simulate_module.norm_implementation_institution_errors() == []
