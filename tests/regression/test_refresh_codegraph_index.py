import subprocess
from types import SimpleNamespace

import engine.simulate as simulate_module


def test_skips_cleanly_when_codegraph_binary_is_missing(monkeypatch):
    monkeypatch.setattr(simulate_module.shutil, "which", lambda name: None)
    calls = []
    monkeypatch.setattr(simulate_module.subprocess, "run", lambda *a, **k: calls.append(a) or None)

    simulate_module.refresh_codegraph_index()  # must not raise

    assert calls == []


def test_runs_unlock_then_removes_dir_then_inits(monkeypatch, tmp_path):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    monkeypatch.setattr(simulate_module.shutil, "which", lambda name: "/usr/bin/codegraph")
    (tmp_path / ".codegraph").mkdir()
    (tmp_path / ".codegraph" / "codegraph.db").write_text("stale")

    calls = []

    def _fake_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(simulate_module.subprocess, "run", _fake_run)

    simulate_module.refresh_codegraph_index()

    assert calls[0] == ["codegraph", "--no-color", "unlock", "."]
    assert calls[1] == ["codegraph", "--no-color", "init", "."]
    # the old .codegraph/ directory content must have been wiped between
    # unlock and init, not left in place for init to build on top of.
    assert not (tmp_path / ".codegraph" / "codegraph.db").exists()


def test_removes_the_index_on_a_failed_init(monkeypatch, tmp_path):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    monkeypatch.setattr(simulate_module.shutil, "which", lambda name: "/usr/bin/codegraph")

    def _fake_run(cmd, **kwargs):
        if cmd[2] == "init":
            (tmp_path / ".codegraph").mkdir(exist_ok=True)
            return SimpleNamespace(returncode=1, stdout="", stderr="boom")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(simulate_module.subprocess, "run", _fake_run)

    simulate_module.refresh_codegraph_index()  # must not raise

    assert not (tmp_path / ".codegraph").exists()


def test_removes_the_index_on_a_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    monkeypatch.setattr(simulate_module.shutil, "which", lambda name: "/usr/bin/codegraph")
    (tmp_path / ".codegraph").mkdir()

    def _fake_run(cmd, **kwargs):
        if cmd[2] == "init":
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=120)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(simulate_module.subprocess, "run", _fake_run)

    simulate_module.refresh_codegraph_index()  # must not raise

    assert not (tmp_path / ".codegraph").exists()
