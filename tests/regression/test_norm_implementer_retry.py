import engine.simulate as simulate_module


def test_succeeds_on_first_attempt_no_sleep_no_extra_calls(monkeypatch):
    calls = []
    sleeps = []
    monkeypatch.setattr(
        simulate_module, "run_norm_implementer",
        lambda round_number, extra_message=None: calls.append("run") or True,
    )
    monkeypatch.setattr(simulate_module.time, "sleep", lambda s: sleeps.append(s))

    assert simulate_module.run_norm_implementer_with_retry(1) is True
    assert calls == ["run"]
    assert sleeps == []


def test_retries_up_to_the_full_budget_with_a_delay_between_each_attempt(monkeypatch):
    attempts = {"n": 0}
    sleeps = []

    def _fake_run(round_number, extra_message=None):
        attempts["n"] += 1
        return attempts["n"] == simulate_module.MAX_IMPLEMENTER_PROCESS_ATTEMPTS

    monkeypatch.setattr(simulate_module, "run_norm_implementer", _fake_run)
    monkeypatch.setattr(simulate_module.time, "sleep", lambda s: sleeps.append(s))

    assert simulate_module.run_norm_implementer_with_retry(1) is True
    assert attempts["n"] == simulate_module.MAX_IMPLEMENTER_PROCESS_ATTEMPTS
    # One sleep between each pair of attempts, never after the final
    # (successful) one.
    assert sleeps == [simulate_module.NORM_IMPLEMENTER_RETRY_DELAY_S] * (simulate_module.MAX_IMPLEMENTER_PROCESS_ATTEMPTS - 1)


def test_returns_false_after_exhausting_every_attempt(monkeypatch):
    attempts = {"n": 0}
    sleeps = []

    def _always_fails(round_number, extra_message=None):
        attempts["n"] += 1
        return False

    monkeypatch.setattr(simulate_module, "run_norm_implementer", _always_fails)
    monkeypatch.setattr(simulate_module.time, "sleep", lambda s: sleeps.append(s))

    assert simulate_module.run_norm_implementer_with_retry(1) is False
    assert attempts["n"] == simulate_module.MAX_IMPLEMENTER_PROCESS_ATTEMPTS
    assert len(sleeps) == simulate_module.MAX_IMPLEMENTER_PROCESS_ATTEMPTS - 1


def test_the_budget_is_actually_five(monkeypatch):
    """Pins the specific value requested (2026-09-14): a persistently
    truncating session should get several real chances before the round
    is discarded, not just two."""
    assert simulate_module.MAX_IMPLEMENTER_PROCESS_ATTEMPTS == 5


def test_every_attempt_starts_a_brand_new_session(monkeypatch):
    """Session continuation across retries (added 2026-09-15) was reverted
    the same month: a real round's continuously-growing session eventually
    became too large for the model to even begin responding to within
    opencode's own internal timeout, burning the whole retry budget on
    calls that could never succeed. Each retry attempt must now be an
    entirely independent run_norm_implementer() call with no session
    threaded through — run_norm_implementer() itself no longer accepts a
    session_id at all."""
    call_count = {"n": 0}

    def _fake_run(round_number, extra_message=None):
        call_count["n"] += 1
        return call_count["n"] == 3

    monkeypatch.setattr(simulate_module, "run_norm_implementer", _fake_run)
    monkeypatch.setattr(simulate_module.time, "sleep", lambda s: None)

    assert simulate_module.run_norm_implementer_with_retry(1) is True
    assert call_count["n"] == 3
