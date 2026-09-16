import engine.simulate as simulate_module


def test_removes_pycache_dirs_at_every_depth(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)

    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "root.pyc").write_text("x")
    (tmp_path / "engine" / "__pycache__").mkdir(parents=True)
    (tmp_path / "engine" / "__pycache__" / "simulate.pyc").write_text("x")
    (tmp_path / "actions" / "rules" / "harvest" / "__pycache__").mkdir(parents=True)
    (tmp_path / "actions" / "rules" / "harvest" / "__pycache__" / "trip_cap.pyc").write_text("x")

    # A real .py file sitting alongside one of the cache dirs must survive.
    (tmp_path / "engine" / "simulate.py").write_text("# real source")

    simulate_module.clean_pycache_dirs()

    assert not (tmp_path / "__pycache__").exists()
    assert not (tmp_path / "engine" / "__pycache__").exists()
    assert not (tmp_path / "actions" / "rules" / "harvest" / "__pycache__").exists()
    assert (tmp_path / "engine" / "simulate.py").is_file()


def test_no_op_and_no_crash_when_none_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(simulate_module, "ROOT", tmp_path)
    simulate_module.clean_pycache_dirs()  # must not raise
