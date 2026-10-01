"""Harness checks added after sim/run-20261001-160838's round 1, which
spent all 10 compile-repair attempts reaching norm-auditor (five of them on
a false positive in the runtime smoke test), then was discarded outright
when its first audit repair introduced one hallucinated import that
pyright had already reported to norm-engineer.

Covers: the runtime smoke test loading the real declared objects; the
per-agent `from: state` hint; gate/scheduling validation; pyright as a
binding check; and auditor-flagged requirements never reported as
"Satisfied"."""
import json
import shutil
import subprocess

import engine.simulate as simulate_module

REPO = simulate_module.ROOT


PROTECTED_ACTION_NAMES = {"harvest", "propose", "critique", "vote", "discuss"}


def _repo_copy(tmp_path):
    """The runtime smoke test runs a subprocess with cwd=ROOT that imports
    the real engine/actions/roles packages, so it can only be exercised
    against a full copy of them — never by monkeypatching ROOT alone.
    Whatever branch happens to be checked out may have its own committed
    rounds' custom actions/objects sitting in state/ — this strips those
    back to the 5 protected actions so each test starts from the same
    baseline regardless, then adds only what it declares itself."""
    for name in ("engine", "actions", "roles", "objects", "state", "constants", "prompts"):
        src = REPO / name
        if src.is_dir():
            shutil.copytree(src, tmp_path / name, ignore=shutil.ignore_patterns("__pycache__"))
    for extra in (tmp_path / "state" / "actions").glob("*.json"):
        if extra.stem not in PROTECTED_ACTION_NAMES:
            extra.unlink()
    for extra_dir in ("object_types",):
        for extra in (tmp_path / "state" / extra_dir).glob("*.json"):
            extra.unlink()
    objects_json = tmp_path / "state" / "objects.json"
    if objects_json.is_file():
        objects_json.write_text("[]")
    institution_path = tmp_path / "state" / "institution.json"
    institution = json.loads(institution_path.read_text())
    institution["actions"] = {
        name: entry for name, entry in institution.get("actions", {}).items()
        if name in PROTECTED_ACTION_NAMES
    }
    institution["object_types"] = {}
    institution_path.write_text(json.dumps(institution))
    for extra in (tmp_path / "actions" / "rules").glob("*"):
        if extra.is_dir() and extra.name not in PROTECTED_ACTION_NAMES:
            shutil.rmtree(extra)
    return tmp_path


def _register_action(root, name, spec):
    (root / "state" / "actions" / f"{name}.json").write_text(json.dumps(spec))
    institution = json.loads((root / "state" / "institution.json").read_text())
    institution["actions"][name] = {"spec": f"state/actions/{name}.json"}
    (root / "state" / "institution.json").write_text(json.dumps(institution))


def _generic_spec(name, fields, gate="true", after=None):
    return {
        "name": name, "description": "x",
        "scheduling": {"gate": gate, "after": after, "before": None},
        "participation": {"policy": "all_alive_fishers"},
        "execution": {"handler": "generic_agent_decision"},
        "prompt": {"template": "Pool holds {pool_kg}.\n{{\"withdraw_amount\": 0}}", "fields": fields},
    }


def _declare_pool(root):
    (root / "state" / "object_types" / "pool.json").write_text(json.dumps({
        "type_name": "pool", "fields": {"total_kg": {"type": "number", "default": 0.0}},
        "permissions": {}, "visibility": {},
    }))
    (root / "state" / "objects.json").write_text(json.dumps([{"id": "communal_pool", "type": "pool"}]))
    institution = json.loads((root / "state" / "institution.json").read_text())
    institution["object_types"] = {"pool": {"description": "x", "owner": "state/object_types/pool.json"}}
    (root / "state" / "institution.json").write_text(json.dumps(institution))


def test_runtime_check_sees_objects_actually_declared_on_disk(tmp_path, monkeypatch):
    root = _repo_copy(tmp_path)
    monkeypatch.setattr(simulate_module, "ROOT", root)
    _declare_pool(root)
    _register_action(root, "withdraw", _generic_spec(
        "withdraw", {"pool_kg": {"from": "object", "object_id": "communal_pool", "field": "total_kg"}},
    ))
    assert simulate_module.norm_implementation_runtime_errors() is None


def test_unreachable_state_path_explains_per_agent_values_need_a_custom_handler(tmp_path, monkeypatch):
    root = _repo_copy(tmp_path)
    monkeypatch.setattr(simulate_module, "ROOT", root)
    _register_action(root, "withdraw", _generic_spec(
        "withdraw", {"pool_kg": {"from": "state", "path": "runtime.current_catch"}},
    ))
    error = simulate_module.norm_implementation_runtime_errors()
    assert error and "can never reach a per-agent value" in error
    assert "build_fields(agent_id)" in error
    assert "never delete the field" in error


def test_ordering_written_into_a_gate_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "state" / "actions").mkdir(parents=True)
    (tmp_path / "state" / "actions" / "harvest.json").write_text(json.dumps(
        {"name": "harvest", "scheduling": {"gate": "something invalid but protected"}}))
    (tmp_path / "state" / "actions" / "record_surplus.json").write_text(json.dumps(
        _generic_spec("record_surplus", {}, gate="after harvest")))
    (tmp_path / "state" / "actions" / "withdraw.json").write_text(json.dumps(
        _generic_spec("withdraw", {}, gate="holdsAt(pool_open)", after="fishing_trip")))
    (tmp_path / "state" / "actions" / "deposit.json").write_text(json.dumps(
        _generic_spec("deposit", {}, gate="true", after="harvest")))

    errors = simulate_module.norm_implementation_schedule_errors()

    assert any("record_surplus.json" in e and "after harvest" in e and "scheduling.after" in e for e in errors)
    assert any("withdraw.json" in e and "fishing_trip" in e for e in errors)
    assert not any("deposit.json" in e for e in errors)
    assert not any("harvest.json" in e for e in errors)  # protected actions are never re-judged
    assert len(errors) == 2


def _fake_pyright(monkeypatch, diagnostics):
    monkeypatch.setattr(simulate_module.shutil, "which", lambda name: "/usr/bin/pyright")
    monkeypatch.setattr(
        simulate_module.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, stdout=json.dumps({"generalDiagnostics": diagnostics}), stderr=""),
    )


def test_pyright_blocks_only_on_code_that_cannot_work(monkeypatch, tmp_path):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    file = str(tmp_path / "actions" / "rules" / "harvest" / "ban.py")
    _fake_pyright(monkeypatch, [
        {"file": file, "severity": "error", "rule": "reportAttributeAccessIssue",
         "message": '"set_fact" is unknown import symbol', "range": {"start": {"line": 2}}},
        {"file": file, "severity": "error", "rule": "reportMissingImports",
         "message": 'Import "engine.state" could not be resolved', "range": {"start": {"line": 3}}},
        {"file": file, "severity": "error", "rule": "reportOptionalOperand",
         "message": "Operator + not supported for None", "range": {"start": {"line": 9}}},
        {"file": file, "severity": "warning", "rule": "reportAttributeAccessIssue",
         "message": "a warning, not an error", "range": {"start": {"line": 1}}},
    ])
    errors = simulate_module._pyright_blocking_errors(["actions/rules/harvest/ban.py"])
    assert errors == [
        'actions/rules/harvest/ban.py:3: "set_fact" is unknown import symbol (reportAttributeAccessIssue)',
        'actions/rules/harvest/ban.py:4: Import "engine.state" could not be resolved (reportMissingImports)',
    ]


def test_pyright_check_degrades_to_nothing_when_pyright_is_missing(monkeypatch):
    monkeypatch.setattr(simulate_module.shutil, "which", lambda name: None)
    assert simulate_module._pyright_blocking_errors(["actions/rules/harvest/ban.py"]) == []


def test_type_errors_name_where_role_and_fact_primitives_really_live(monkeypatch):
    monkeypatch.setattr(simulate_module, "_changed_norm_python_files", lambda: ["x.py"])
    monkeypatch.setattr(simulate_module, "_pyright_blocking_errors",
                        lambda files: ['x.py:1: "set_fact" is unknown import symbol (reportAttributeAccessIssue)'])
    [error] = simulate_module.norm_implementation_type_errors()
    assert "set_fact" in error and "roles.roles" in error


def test_auditor_flagged_ids_come_from_the_verdict_line_when_there_is_one():
    known = {"R1", "R4", "R7", "R12", "R13"}
    report = ("Plan maps this through R4 and R12 (both pass).\n"
              "AUDIT_FAILED: Requirements R12 and R13 are under-enforced.")
    assert simulate_module._audit_flagged_requirement_ids(report, known) == {"R12", "R13"}
    assert simulate_module._audit_flagged_requirement_ids("R7 is under-enforced.", known) == {"R7"}


def test_an_auditor_flagged_requirement_is_never_listed_as_satisfied():
    evidence = {f"R{i}": [f"acceptance test test_R{i}_x: PASS"] for i in (1, 7)}
    block = simulate_module._render_requirement_status_block(evidence, flagged_by_auditor={"R7"})
    satisfied_line = next(line for line in block.splitlines() if line.startswith("Satisfied"))
    assert "R7" not in satisfied_line
    assert "Flagged by the auditor" in block and "R7" in block
