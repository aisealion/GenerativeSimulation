import engine.simulate as simulate_module


def test_clears_a_stale_lock_at_any_depth(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module.Path, "home", classmethod(lambda cls: tmp_path))
    snapshot_dir = tmp_path / ".local" / "share" / "opencode" / "snapshot" / "proj_hash" / "track_hash"
    snapshot_dir.mkdir(parents=True)
    lock = snapshot_dir / "index.lock"
    lock.write_text("")

    simulate_module.clear_stale_opencode_snapshot_lock()

    assert not lock.exists()


def test_no_op_and_no_crash_when_snapshot_dir_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module.Path, "home", classmethod(lambda cls: tmp_path))
    simulate_module.clear_stale_opencode_snapshot_lock()  # must not raise


def test_no_op_when_no_lock_present(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module.Path, "home", classmethod(lambda cls: tmp_path))
    snapshot_dir = tmp_path / ".local" / "share" / "opencode" / "snapshot" / "proj_hash" / "track_hash"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "some_other_file.json").write_text("{}")

    simulate_module.clear_stale_opencode_snapshot_lock()  # must not raise

    assert (snapshot_dir / "some_other_file.json").exists()
