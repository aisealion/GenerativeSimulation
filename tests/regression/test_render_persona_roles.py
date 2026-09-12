import json

import pytest

import engine.llm_agents as llm_agents_module
from engine.llm_agents import render_role_directives
from roles.roles import assign_role, set_fact


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _setup(tmp_path, monkeypatch, roles):
    monkeypatch.setattr(llm_agents_module, "ROOT", tmp_path)
    _write(tmp_path / "state" / "institution.json", json.dumps({"roles": roles}))


def test_renders_every_currently_held_registered_role_in_catalog_order(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, {"fisher": {}, "recorder": {}})
    _write(tmp_path / "prompts" / "role_directives" / "fisher.md", "Fisher text.")
    _write(tmp_path / "prompts" / "role_directives" / "recorder.md", "Recorder text.")

    fluents = []
    assign_role("fisher", "agent_0", fluents, 0)
    assign_role("recorder", "agent_0", fluents, 0, exclusive=True)

    assert render_role_directives("agent_0", fluents, 0) == "Fisher text. Recorder text."


def test_only_renders_roles_this_specific_agent_actually_holds(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, {"fisher": {}, "recorder": {}})
    _write(tmp_path / "prompts" / "role_directives" / "fisher.md", "Fisher text.")
    _write(tmp_path / "prompts" / "role_directives" / "recorder.md", "Recorder text.")

    fluents = []
    assign_role("fisher", "agent_0", fluents, 0)
    assign_role("fisher", "agent_1", fluents, 0)
    assign_role("recorder", "agent_1", fluents, 0, exclusive=True)

    assert render_role_directives("agent_0", fluents, 0) == "Fisher text."
    assert render_role_directives("agent_1", fluents, 0) == "Fisher text. Recorder text."


def test_raises_for_a_held_role_with_no_directive_file(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, {"fisher": {}, "recorder": {}})
    _write(tmp_path / "prompts" / "role_directives" / "fisher.md", "Fisher text.")
    # recorder.md deliberately not written.

    fluents = []
    assign_role("fisher", "agent_0", fluents, 0)
    assign_role("recorder", "agent_0", fluents, 0, exclusive=True)

    with pytest.raises(FileNotFoundError, match="recorder"):
        render_role_directives("agent_0", fluents, 0)


def test_a_fluent_that_isnt_a_registered_role_is_never_treated_as_one(tmp_path, monkeypatch):
    """A fluent name that happens to exist (a sanction, a status) but
    isn't in state/institution.json's own "roles" catalog must never be
    read as a role directive — only catalog-registered names are looked
    up, so an unrelated fact can never accidentally require a directive
    file that was never meant to exist."""
    _setup(tmp_path, monkeypatch, {"fisher": {}})
    _write(tmp_path / "prompts" / "role_directives" / "fisher.md", "Fisher text.")

    fluents = []
    assign_role("fisher", "agent_0", fluents, 0)
    set_fact(fluents, "banned", ["agent_0"], "agent_0", 0)

    assert render_role_directives("agent_0", fluents, 0) == "Fisher text."


def test_a_role_no_agent_holds_yet_needs_no_directive_file(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, {"fisher": {}, "treasurer": {}})
    _write(tmp_path / "prompts" / "role_directives" / "fisher.md", "Fisher text.")
    # treasurer.md deliberately absent — fine, since nobody holds it yet.

    fluents = []
    assign_role("fisher", "agent_0", fluents, 0)

    assert render_role_directives("agent_0", fluents, 0) == "Fisher text."
