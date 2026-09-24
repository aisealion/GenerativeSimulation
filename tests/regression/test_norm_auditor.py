"""norm-auditor stopped running through opencode on 2026-09-23 — the same
fix as norm-architect (call_norm_auditor_agent() in engine/llm_agents.py):
DeepSeek-R1 doesn't support tool calling on Ollama, and the auditor never
actually needed real tools either.

2026-09-24: reworked again (by request) to review a structured evidence
package instead of a raw git diff — norm-architect's own frozen
norm_plan.json plus _gather_norm_evidence()'s per-requirement evidence
(state/norm_specs' verified claims + acceptance-test PASS/FAIL). The
question run_norm_auditor() poses is now "does this evidence demonstrate
the norm was actually instantiated?", not "does this diff look right?" —
still catching the same failure class (code that compiles, passes its own
tests, and is still quietly wrong, e.g. a >10%-over-quota / else-lesser-
fine threshold collapsed into one flat fine), just from richer input.
These tests monkeypatch _gather_norm_evidence() itself rather than running
a real pytest subprocess — that function has its own dedicated tests in
tests/regression/test_norm_evidence.py."""
import json

import engine.simulate as simulate_module


def _write_plan(tmp_path, round_number=4, requirements=None):
    plan = {
        "requirements": requirements if requirements is not None else [
            {"id": "R1", "type": "RULE", "description": "10% threshold fine split"},
        ],
        "open_critiques": [],
    }
    plan_dir = tmp_path / "tests" / "norm_checks" / f"round_{round_number}"
    plan_dir.mkdir(parents=True)
    (plan_dir / "norm_plan.json").write_text(json.dumps(plan))
    return plan


def test_returns_compliant_when_audit_passed_sentinel_is_present(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    _write_plan(tmp_path)
    monkeypatch.setattr(simulate_module, "_gather_norm_evidence", lambda round_number, plan: {"R1": ["PASS"]})
    monkeypatch.setattr(
        simulate_module, "call_norm_auditor_agent",
        lambda round_number, norm_text, plan, evidence: "Everything checks out.\n\nAUDIT_PASSED",
    )

    result = simulate_module.run_norm_auditor(4)

    assert result == {"result": "COMPLIANT", "text": "Everything checks out.\n\nAUDIT_PASSED"}


def test_returns_needs_repair_when_audit_passed_sentinel_is_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    _write_plan(tmp_path)
    monkeypatch.setattr(simulate_module, "_gather_norm_evidence", lambda round_number, plan: {"R1": ["FAIL"]})
    critique = "R1: the norm requires a 10% threshold split but the evidence shows a flat $5,000 fine."
    monkeypatch.setattr(
        simulate_module, "call_norm_auditor_agent",
        lambda round_number, norm_text, plan, evidence: critique,
    )

    result = simulate_module.run_norm_auditor(4)

    assert result == {"result": "NEEDS_REPAIR", "text": critique}


def test_returns_none_when_the_completion_call_itself_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    _write_plan(tmp_path)
    monkeypatch.setattr(simulate_module, "_gather_norm_evidence", lambda round_number, plan: {"R1": []})
    monkeypatch.setattr(
        simulate_module, "call_norm_auditor_agent",
        lambda round_number, norm_text, plan, evidence: None,
    )

    assert simulate_module.run_norm_auditor(4) is None


def test_returns_none_when_norm_txt_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)  # no norm.txt written
    _write_plan(tmp_path)

    def _unexpected_call(round_number, norm_text, plan, evidence):
        raise AssertionError("should never call the auditor with no norm.txt to audit against")

    monkeypatch.setattr(simulate_module, "call_norm_auditor_agent", _unexpected_call)

    assert simulate_module.run_norm_auditor(4) is None


def test_returns_none_when_norm_plan_json_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    # no tests/norm_checks/round_4/norm_plan.json written

    def _unexpected_call(round_number, norm_text, plan, evidence):
        raise AssertionError("should never call the auditor with no frozen plan to audit against")

    monkeypatch.setattr(simulate_module, "call_norm_auditor_agent", _unexpected_call)

    assert simulate_module.run_norm_auditor(4) is None


def test_returns_none_when_norm_plan_json_is_invalid(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    plan_dir = tmp_path / "tests" / "norm_checks" / "round_4"
    plan_dir.mkdir(parents=True)
    (plan_dir / "norm_plan.json").write_text("{not valid json")

    def _unexpected_call(round_number, norm_text, plan, evidence):
        raise AssertionError("should never call the auditor with an unparsable plan")

    monkeypatch.setattr(simulate_module, "call_norm_auditor_agent", _unexpected_call)

    assert simulate_module.run_norm_auditor(4) is None


def test_evidence_and_plan_are_forwarded_to_the_auditor_call(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text("Policy: ...\n\nOperationalization: ...\n")
    plan = _write_plan(tmp_path)
    fake_evidence = {"R1": ["acceptance test test_R1_over_quota: PASS"]}
    monkeypatch.setattr(simulate_module, "_gather_norm_evidence", lambda round_number, p: fake_evidence)

    captured = {}

    def _fake_call(round_number, norm_text, forwarded_plan, forwarded_evidence):
        captured["plan"] = forwarded_plan
        captured["evidence"] = forwarded_evidence
        return "AUDIT_PASSED"

    monkeypatch.setattr(simulate_module, "call_norm_auditor_agent", _fake_call)

    simulate_module.run_norm_auditor(4)

    assert captured["plan"] == plan
    assert captured["evidence"] == fake_evidence
