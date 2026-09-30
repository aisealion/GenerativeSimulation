"""_restore_protected_paths() (engine/simulate.py): a real round's own
cleanup script globbed every file in state/actions/ instead of just its
own new ones, and its write call sat outside the guard that should have
skipped files needing no change -- rewriting the 5 protected actions'
bytes as a pure side effect, no logical change. norm_implementation_
protected_path_violations() correctly caught the byte-level diff and
discarded an otherwise-good round over it.  _restore_protected_paths()
now runs right before that check, so an incidental touch like this
self-heals instead of costing the whole round. Exercises the real `git`
subprocess calls directly, like test_discard_norm_implementation.py
does -- the bug (and the fix) is specifically in what those commands do."""
import subprocess

import engine.simulate as simulate_module


def _git(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(tmp_path):
    _git(["init"], tmp_path)
    _git(["config", "user.email", "test@test"], tmp_path)
    _git(["config", "user.name", "test"], tmp_path)
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "institution.json").write_text("{}\n")
    (tmp_path / "state" / "actions").mkdir()
    (tmp_path / "state" / "actions" / "harvest.json").write_text('{"name": "harvest"}\n')
    _git(["add", "-A"], tmp_path)
    _git(["commit", "-m", "initial"], tmp_path)


def test_restore_reverts_an_incidental_rewrite_of_a_protected_file(monkeypatch, tmp_path):
    _init_repo(tmp_path)
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    monkeypatch.setattr(simulate_module, "PROTECTED_PATHS", ["state/actions/harvest.json"])

    protected_file = tmp_path / "state" / "actions" / "harvest.json"
    protected_file.write_text('{"name":"harvest","execution":{"handler":"harvest"}}\n')

    simulate_module._restore_protected_paths()

    assert protected_file.read_text() == '{"name": "harvest"}\n'
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True, check=True,
    ).stdout
    assert status == ""


def test_restore_tolerates_a_protected_path_that_never_existed(monkeypatch, tmp_path):
    _init_repo(tmp_path)
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    # PROTECTED_PATHS includes a builtin handler's derived .py path even
    # when no such file exists (see _actions_protected_as_of_head()'s own
    # docstring) -- a single nonexistent pathspec must never block the
    # restore of every OTHER real protected path in the same call.
    monkeypatch.setattr(
        simulate_module, "PROTECTED_PATHS",
        ["state/actions/harvest.json", "actions/handlers/nonexistent_builtin.py"],
    )

    protected_file = tmp_path / "state" / "actions" / "harvest.json"
    protected_file.write_text('{"name":"harvest","execution":{"handler":"harvest"}}\n')

    simulate_module._restore_protected_paths()  # must not raise

    assert protected_file.read_text() == '{"name": "harvest"}\n'


def test_restore_removes_an_untracked_new_file_under_a_protected_directory(monkeypatch, tmp_path):
    _init_repo(tmp_path)
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    (tmp_path / "engine" / "institution").mkdir(parents=True)
    monkeypatch.setattr(simulate_module, "PROTECTED_PATHS", ["engine/institution"])

    stray_file = tmp_path / "engine" / "institution" / "stray.py"
    stray_file.write_text("# should never survive a restore\n")

    simulate_module._restore_protected_paths()

    assert not stray_file.exists()
