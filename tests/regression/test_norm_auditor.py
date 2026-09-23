"""norm-auditor stopped running through opencode on 2026-09-23 — the same
fix as norm-architect (call_norm_auditor_agent() in engine/llm_agents.py):
DeepSeek-R1 doesn't support tool calling on Ollama, and the auditor never
actually needed real tools either — its job is cross-referencing two
fixed texts (norm.txt and the round's diff), which a plain completion
call does exactly as well. It also no longer writes its own independent
pytest suite (tests/norm_evaluation/round_N/) — a direct text-level
cross-reference of norm vs. code, by request, catches the exact failure
class that matters (code that compiles, passes its own tests, and is
still quietly wrong — e.g. a >10%-over-quota / else-lesser-fine threshold
collapsed into one flat fine) without needing that."""
from types import SimpleNamespace

import engine.simulate as simulate_module


def _fake_completed_process(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_returns_compliant_when_audit_passed_sentinel_is_present(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    monkeypatch.setattr(simulate_module.subprocess, "run", lambda *a, **k: _fake_completed_process())
    monkeypatch.setattr(
        simulate_module, "call_norm_auditor_agent",
        lambda round_number, norm_text, diff_text: "Everything checks out.\n\nAUDIT_PASSED",
    )

    result = simulate_module.run_norm_auditor(4)

    assert result == {"result": "COMPLIANT", "text": "Everything checks out.\n\nAUDIT_PASSED"}


def test_returns_needs_repair_when_audit_passed_sentinel_is_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    monkeypatch.setattr(simulate_module.subprocess, "run", lambda *a, **k: _fake_completed_process())
    critique = "The norm requires a 10% threshold split but the code applies a flat $5,000 fine."
    monkeypatch.setattr(
        simulate_module, "call_norm_auditor_agent",
        lambda round_number, norm_text, diff_text: critique,
    )

    result = simulate_module.run_norm_auditor(4)

    assert result == {"result": "NEEDS_REPAIR", "text": critique}


def test_returns_none_when_the_completion_call_itself_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    monkeypatch.setattr(simulate_module.subprocess, "run", lambda *a, **k: _fake_completed_process())
    monkeypatch.setattr(
        simulate_module, "call_norm_auditor_agent",
        lambda round_number, norm_text, diff_text: None,
    )

    assert simulate_module.run_norm_auditor(4) is None


def test_returns_none_when_norm_txt_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)  # no norm.txt written

    def _unexpected_call(round_number, norm_text, diff_text):
        raise AssertionError("should never call the auditor with no norm.txt to audit against")

    monkeypatch.setattr(simulate_module, "call_norm_auditor_agent", _unexpected_call)

    assert simulate_module.run_norm_auditor(4) is None


def test_diff_text_combines_tracked_diff_and_untracked_new_files(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    new_rule = tmp_path / "actions" / "rules" / "harvest" / "example_cap.py"
    new_rule.parent.mkdir(parents=True)
    new_rule.write_text("class ExampleCap:\n    pass\n")

    calls = []

    def _fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1] == "diff":
            return _fake_completed_process(stdout="diff --git a/state/config.json b/state/config.json\n")
        assert cmd[1] == "status"
        return _fake_completed_process(stdout="?? actions/rules/harvest/example_cap.py\n")

    monkeypatch.setattr(simulate_module.subprocess, "run", _fake_run)

    diff_text = simulate_module._norm_round_diff_text()

    assert "state/config.json" in diff_text
    assert "class ExampleCap" in diff_text
    assert "actions/rules/harvest/example_cap.py" in diff_text
    # Both git invocations scoped to NORM_ENGINEER_CODE_PATHS, not the
    # broader NORM_ROUND_TRACKED_PATHS (which includes norm-architect's
    # own tests/norm_checks/ — the auditor judges code against the norm
    # text directly, not against a pre-written test's own expectations).
    for cmd in calls:
        assert "tests/norm_checks" not in cmd
        paths = cmd[3:] if cmd[1] == "diff" else cmd[4:]
        assert paths == simulate_module.NORM_ENGINEER_CODE_PATHS


def test_diff_text_falls_back_to_a_placeholder_when_nothing_changed(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    monkeypatch.setattr(simulate_module.subprocess, "run", lambda *a, **k: _fake_completed_process(stdout=""))

    assert simulate_module._norm_round_diff_text() == "(no changes found)"
