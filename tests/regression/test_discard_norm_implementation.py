"""discard_norm_implementation() (engine/simulate.py): a real round showed
norm-engineer running `git add` on its own new files despite its own
standing instruction never to (its shell permission is unrestricted, so
nothing technically blocked it) — once staged, `git clean -fd` no longer
considers those files untracked, so a "discarded" round's own code
silently survived and got swept into the next real commit regardless.
These exercise the real `git` subprocess calls directly (unlike every
other discard-related test, which monkeypatches discard_norm_implementation
itself out) — the bug is specifically in what those real commands do."""
import subprocess

import engine.simulate as simulate_module


def _git(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(tmp_path):
    _git(["init"], tmp_path)
    _git(["config", "user.email", "test@test"], tmp_path)
    _git(["config", "user.name", "test"], tmp_path)
    (tmp_path / "actions").mkdir()
    (tmp_path / "actions" / "keep.txt").write_text("already committed\n")
    _git(["add", "actions/keep.txt"], tmp_path)
    _git(["commit", "-m", "initial"], tmp_path)


def test_discard_removes_a_file_norm_engineer_staged_itself_against_instructions(monkeypatch, tmp_path):
    _init_repo(tmp_path)
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    monkeypatch.setattr(simulate_module, "log_call", lambda **kwargs: None)

    new_file = tmp_path / "actions" / "handlers" / "sneaky.py"
    new_file.parent.mkdir(parents=True, exist_ok=True)
    new_file.write_text("def run(ctx): pass\n")
    _git(["add", "actions/handlers/sneaky.py"], tmp_path)

    simulate_module.discard_norm_implementation(1, ["test discard"])

    assert not new_file.exists()
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True, check=True,
    ).stdout
    assert status == ""


def test_discard_still_reverts_an_edit_to_an_already_committed_tracked_file(monkeypatch, tmp_path):
    _init_repo(tmp_path)
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    monkeypatch.setattr(simulate_module, "log_call", lambda **kwargs: None)

    tracked_file = tmp_path / "actions" / "keep.txt"
    tracked_file.write_text("norm-engineer overwrote this\n")
    _git(["add", "actions/keep.txt"], tmp_path)  # also staged, same as the sneaky case

    simulate_module.discard_norm_implementation(1, ["test discard"])

    assert tracked_file.read_text() == "already committed\n"
