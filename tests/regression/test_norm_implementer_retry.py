import engine.simulate as simulate_module


def test_succeeds_on_first_attempt_no_sleep_no_extra_calls(monkeypatch):
    calls = []
    sleeps = []
    monkeypatch.setattr(simulate_module, "refresh_knowledge_graph", lambda round_number: calls.append("refresh"))
    monkeypatch.setattr(simulate_module, "run_norm_implementer", lambda round_number, extra_message=None: calls.append("run") or True)
    monkeypatch.setattr(simulate_module.time, "sleep", lambda s: sleeps.append(s))

    assert simulate_module.run_norm_implementer_with_retry(1) is True
    assert calls == ["refresh", "run"]
    assert sleeps == []


def test_retries_up_to_the_full_budget_with_a_delay_between_each_attempt(monkeypatch):
    attempts = {"n": 0}
    sleeps = []

    def _fake_run(round_number, extra_message=None):
        attempts["n"] += 1
        return attempts["n"] == simulate_module.MAX_IMPLEMENTER_PROCESS_ATTEMPTS

    monkeypatch.setattr(simulate_module, "refresh_knowledge_graph", lambda round_number: None)
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

    monkeypatch.setattr(simulate_module, "refresh_knowledge_graph", lambda round_number: None)
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
