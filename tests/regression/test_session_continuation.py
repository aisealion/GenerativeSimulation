import json
from types import SimpleNamespace

import engine.simulate as simulate_module


def _jsonl(*events):
    return "\n".join(json.dumps(e) for e in events)


def _implementer_success_stdout(session_id):
    return _jsonl(
        {"type": "step_start", "sessionID": session_id, "part": {"messageID": "m1"}},
        {"type": "tool_use", "sessionID": session_id, "part": {"tool": "read", "state": {}}},
        {"type": "text", "sessionID": session_id, "part": {"messageID": "m1", "text": '```json\n{"classification": []}\n```'}},
        {"type": "step_finish", "sessionID": session_id, "part": {"reason": "stop"}},
    )


def _evaluator_compliant_stdout(session_id):
    return _jsonl(
        {"type": "step_start", "sessionID": session_id, "part": {"messageID": "m1"}},
        {"type": "tool_use", "sessionID": session_id, "part": {"tool": "read", "state": {}}},
        {"type": "text", "sessionID": session_id, "part": {"messageID": "m1", "text": "EVALUATION_RESULT: COMPLIANT"}},
        {"type": "step_finish", "sessionID": session_id, "part": {"reason": "stop"}},
    )


def test_run_norm_implementer_omits_session_flag_on_a_fresh_start(monkeypatch):
    captured_cmds = []

    def _fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        return SimpleNamespace(returncode=0, stdout=_implementer_success_stdout("ses_new"), stderr="")

    monkeypatch.setattr(simulate_module.subprocess, "run", _fake_run)
    monkeypatch.setattr(simulate_module, "log_call", lambda *a, **k: None)

    success, session_id = simulate_module.run_norm_implementer(1, session_id=None)
    assert success is True
    assert session_id == "ses_new"
    assert "--session" not in captured_cmds[0]


def test_run_norm_implementer_passes_session_flag_when_continuing(monkeypatch):
    captured_cmds = []

    def _fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        return SimpleNamespace(returncode=0, stdout=_implementer_success_stdout("ses_existing"), stderr="")

    monkeypatch.setattr(simulate_module.subprocess, "run", _fake_run)
    monkeypatch.setattr(simulate_module, "log_call", lambda *a, **k: None)

    success, session_id = simulate_module.run_norm_implementer(1, session_id="ses_existing")
    assert success is True
    assert session_id == "ses_existing"
    cmd = captured_cmds[0]
    idx = cmd.index("--session")
    assert cmd[idx + 1] == "ses_existing"


def test_run_norm_evaluator_omits_session_flag_on_a_fresh_start(monkeypatch):
    captured_cmds = []

    def _fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        return SimpleNamespace(returncode=0, stdout=_evaluator_compliant_stdout("ses_new"), stderr="")

    monkeypatch.setattr(simulate_module.subprocess, "run", _fake_run)
    monkeypatch.setattr(simulate_module, "log_call", lambda *a, **k: None)

    evaluation, session_id = simulate_module.run_norm_evaluator(1, session_id=None)
    assert evaluation == {"result": "COMPLIANT", "text": "EVALUATION_RESULT: COMPLIANT"}
    assert session_id == "ses_new"
    assert "--session" not in captured_cmds[0]


def test_run_norm_evaluator_passes_session_flag_when_continuing(monkeypatch):
    captured_cmds = []

    def _fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        return SimpleNamespace(returncode=0, stdout=_evaluator_compliant_stdout("ses_existing"), stderr="")

    monkeypatch.setattr(simulate_module.subprocess, "run", _fake_run)
    monkeypatch.setattr(simulate_module, "log_call", lambda *a, **k: None)

    evaluation, session_id = simulate_module.run_norm_evaluator(1, session_id="ses_existing")
    assert evaluation["result"] == "COMPLIANT"
    assert session_id == "ses_existing"
    cmd = captured_cmds[0]
    idx = cmd.index("--session")
    assert cmd[idx + 1] == "ses_existing"


def test_run_norm_implementer_preserves_prior_session_id_if_extraction_fails(monkeypatch):
    """A malformed/unparseable stdout must not regress a retry back to
    "no session" — the caller's own session_id is kept as a fallback,
    regardless of what extract_last_step_reason() itself makes of the
    same malformed input (pre-existing, unrelated behavior — a None
    last_step_reason from unparseable output is not treated as a
    truncation by run_norm_implementer(), only a real non-"stop" reason
    is)."""
    def _fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="not valid jsonl at all", stderr="")

    monkeypatch.setattr(simulate_module.subprocess, "run", _fake_run)
    monkeypatch.setattr(simulate_module, "log_call", lambda *a, **k: None)

    success, session_id = simulate_module.run_norm_implementer(1, session_id="ses_kept")
    assert session_id == "ses_kept"


def test_extract_session_id_finds_it_returns_none_when_absent_or_malformed():
    assert simulate_module.extract_session_id(_implementer_success_stdout("ses_abc")) == "ses_abc"
    assert simulate_module.extract_session_id("") is None
    assert simulate_module.extract_session_id("not json") is None
    assert simulate_module.extract_session_id(json.dumps({"type": "step_finish", "part": {"reason": "stop"}})) is None
