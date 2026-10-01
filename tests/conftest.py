"""Keeps the test suite from rewriting the developer's real working tree.

Several harness functions in engine/simulate.py run git commands or delete
files under ROOT: _restore_protected_paths() (`git checkout HEAD --` on every
protected path), discard_norm_implementation() (`git reset`/`checkout`/
`clean -fd` on every norm-round path), stage_norm_implementation()
(`git add`), _clear_stale_round_checks() and _preserve_attempt_log(). Any
test that drives implement_and_evaluate_norm() without stubbing one of them
runs it against the real repository. That silently reverted uncommitted
edits to protected files (engine/institution/, state/actions/) on every test
run, and it looked like an unrelated process undoing the work.

This fixture wraps each of them so that, when ROOT still points at the real
repository, the call is a no-op returning a neutral value. Tests that point
ROOT at a tmp_path, which is how every test exercising these functions
does it, run the real implementation unchanged.
"""
import pytest

import engine.simulate as simulate_module

REAL_ROOT = simulate_module.ROOT.resolve()

_GUARDED = {
    "_restore_protected_paths": lambda *a, **k: None,
    "discard_norm_implementation": lambda *a, **k: None,
    "stage_norm_implementation": lambda *a, **k: True,
    "_clear_stale_round_checks": lambda *a, **k: None,
    "_preserve_attempt_log": lambda round_number, snapshot: snapshot,
}


@pytest.fixture(autouse=True)
def _never_touch_the_real_working_tree(monkeypatch):
    for name, neutral in _GUARDED.items():
        original = getattr(simulate_module, name)

        def guarded(*args, _original=original, _neutral=neutral, **kwargs):
            if simulate_module.ROOT.resolve() == REAL_ROOT:
                return _neutral(*args, **kwargs)
            return _original(*args, **kwargs)

        monkeypatch.setattr(simulate_module, name, guarded)
