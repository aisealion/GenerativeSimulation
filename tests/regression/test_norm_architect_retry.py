"""norm-architect stopped running through opencode on 2026-09-22 — a real
HPC run showed every invocation failing instantly with a 400 API error
("does not support tools"), because Ollama's deepseek-r1 registry tags
don't ship a tool-calling chat template (opencode always sends a `tools`
field; a plain completion call never does). It's now a direct, tool-free
litellm completion (call_norm_architect_agent() in engine/llm_agents.py)
that returns raw text; engine.simulate.run_norm_architect() extracts a
fenced ```python test file and a fenced ```json requirements block from
that text and writes the test file to disk itself, since the model has no
write tool of its own any more. These tests replace the old paired-
opencode-session retry tests, which asserted mechanics (session
continuation, a 5-attempt process-retry budget) that no longer exist —
retries now live inside call_norm_architect_agent() itself, the same
place call_fisher_agent's/call_critique_agent's own retry loops live."""
import json

import engine.simulate as simulate_module


def _requirements_json(**overrides):
    payload = {
        "requirements": [{"requirement": "example", "clarity": "CLEAR"}],
        "open_critiques": [],
    }
    payload.update(overrides)
    return payload


def _response(code="def test_example():\n    assert False\n", report=None, open_critiques=()):
    report = report if report is not None else _requirements_json(open_critiques=list(open_critiques))
    return f"```python\n{code}```\n\n```json\n{json.dumps(report)}\n```\n"


def test_writes_the_test_file_and_returns_the_report_on_a_clean_response(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    calls = []
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None: (
            calls.append(resolutions) or _response()
        ),
    )

    success, report = simulate_module.run_norm_architect(3)

    assert success is True
    assert report["requirements"][0]["requirement"] == "example"
    assert calls == [None]  # no second, finalizing call when there's nothing to resolve
    written = tmp_path / "tests" / "norm_checks" / "round_3" / "test_round_3.py"
    assert written.is_file()
    assert "def test_example" in written.read_text()


def test_returns_false_when_the_completion_call_itself_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None: None,
    )

    success, report = simulate_module.run_norm_architect(3)

    assert success is False
    assert report is None
    assert not (tmp_path / "tests").exists()


def test_returns_false_when_response_has_no_python_block(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None: (
            f"```json\n{json.dumps(_requirements_json())}\n```\n"
        ),
    )

    success, report = simulate_module.run_norm_architect(3)

    assert success is False
    assert report is None


def test_returns_false_when_response_has_no_requirements_key(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None: _response(
            report={"something_else": True},
        ),
    )

    success, report = simulate_module.run_norm_architect(3)

    assert success is False
    assert report is None


def test_returns_false_when_the_written_test_file_does_not_even_compile(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    monkeypatch.setattr(
        simulate_module, "call_norm_architect_agent",
        lambda round_number, norm_text, context_bundle, resolutions=None: _response(
            code="def test_broken(:\n    pass\n",  # syntax error
        ),
    )

    success, report = simulate_module.run_norm_architect(3)

    assert success is False
    assert report is None


def test_resolves_open_critiques_and_uses_the_finalizing_pass_output(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")

    first_response = _response(
        code="def test_draft():\n    assert False\n",
        open_critiques=[{"requirement": "example", "critique_question": "what governs here?"}],
    )
    final_response = _response(code="def test_final():\n    assert False\n")
    pass_count = {"n": 0}

    def _fake_call(round_number, norm_text, context_bundle, resolutions=None):
        pass_count["n"] += 1
        if resolutions is None:
            return first_response
        assert resolutions == [{"critique_question": "what governs here?", "answer": "the later clause"}]
        return final_response

    asked = []

    def _fake_ask(round_number, question):
        asked.append(question)
        return {"answer": "the later clause", "reasoning": "..."}

    monkeypatch.setattr(simulate_module, "call_norm_architect_agent", _fake_call)
    monkeypatch.setattr(simulate_module, "ask_norm_proposer", _fake_ask)

    success, report = simulate_module.run_norm_architect(7)

    assert success is True
    assert pass_count["n"] == 2  # draft pass + finalizing pass
    assert asked == ["what governs here?"]
    written = (tmp_path / "tests" / "norm_checks" / "round_7" / "test_round_7.py").read_text()
    assert "def test_final" in written  # the finalizing pass's output won, not the draft


def test_caps_critique_resolution_at_the_shared_round_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    many_critiques = [
        {"requirement": f"r{i}", "critique_question": f"question {i}?"} for i in range(8)
    ]

    def _fake_call(round_number, norm_text, context_bundle, resolutions=None):
        if resolutions is None:
            return _response(open_critiques=many_critiques)
        return _response()

    asked = []
    monkeypatch.setattr(simulate_module, "call_norm_architect_agent", _fake_call)
    monkeypatch.setattr(
        simulate_module, "ask_norm_proposer",
        lambda round_number, question: (asked.append(question) or {"answer": "ok"}),
    )

    success, _ = simulate_module.run_norm_architect(1)

    assert success is True
    assert len(asked) == simulate_module.MAX_NORM_CLARIFICATIONS_PER_ROUND


def test_run_norm_architect_with_retry_is_a_thin_passthrough(monkeypatch):
    monkeypatch.setattr(simulate_module, "run_norm_architect", lambda round_number: (True, {"requirements": []}))
    assert simulate_module.run_norm_architect_with_retry(9) == (True, {"requirements": []})
