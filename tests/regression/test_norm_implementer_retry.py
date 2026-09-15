import engine.simulate as simulate_module


def test_succeeds_on_first_attempt_no_sleep_no_extra_calls(monkeypatch):
    calls = []
    sleeps = []
    monkeypatch.setattr(simulate_module, "refresh_knowledge_graph", lambda round_number: calls.append("refresh"))
    monkeypatch.setattr(
        simulate_module, "run_norm_implementer",
        lambda round_number, extra_message=None, session_id=None: (calls.append("run") or True, "ses_1"),
    )
    monkeypatch.setattr(simulate_module.time, "sleep", lambda s: sleeps.append(s))

    assert simulate_module.run_norm_implementer_with_retry(1) == (True, "ses_1")
    assert calls == ["refresh", "run"]
    assert sleeps == []


def test_retries_up_to_the_full_budget_with_a_delay_between_each_attempt(monkeypatch):
    attempts = {"n": 0}
    sleeps = []

    def _fake_run(round_number, extra_message=None, session_id=None):
        attempts["n"] += 1
        return attempts["n"] == simulate_module.MAX_IMPLEMENTER_PROCESS_ATTEMPTS, "ses_1"

    monkeypatch.setattr(simulate_module, "refresh_knowledge_graph", lambda round_number: None)
    monkeypatch.setattr(simulate_module, "run_norm_implementer", _fake_run)
    monkeypatch.setattr(simulate_module.time, "sleep", lambda s: sleeps.append(s))

    assert simulate_module.run_norm_implementer_with_retry(1) == (True, "ses_1")
    assert attempts["n"] == simulate_module.MAX_IMPLEMENTER_PROCESS_ATTEMPTS
    # One sleep between each pair of attempts, never after the final
    # (successful) one.
    assert sleeps == [simulate_module.NORM_IMPLEMENTER_RETRY_DELAY_S] * (simulate_module.MAX_IMPLEMENTER_PROCESS_ATTEMPTS - 1)


def test_returns_false_after_exhausting_every_attempt(monkeypatch):
    attempts = {"n": 0}
    sleeps = []

    def _always_fails(round_number, extra_message=None, session_id=None):
        attempts["n"] += 1
        return False, "ses_1"

    monkeypatch.setattr(simulate_module, "refresh_knowledge_graph", lambda round_number: None)
    monkeypatch.setattr(simulate_module, "run_norm_implementer", _always_fails)
    monkeypatch.setattr(simulate_module.time, "sleep", lambda s: sleeps.append(s))

    assert simulate_module.run_norm_implementer_with_retry(1) == (False, "ses_1")
    assert attempts["n"] == simulate_module.MAX_IMPLEMENTER_PROCESS_ATTEMPTS
    assert len(sleeps) == simulate_module.MAX_IMPLEMENTER_PROCESS_ATTEMPTS - 1


def test_the_budget_is_actually_five(monkeypatch):
    """Pins the specific value requested (2026-09-14): a persistently
    truncating session should get several real chances before the round
    is discarded, not just two."""
    assert simulate_module.MAX_IMPLEMENTER_PROCESS_ATTEMPTS == 5


def test_a_retry_continues_the_same_session_a_fresh_start_does_not(monkeypatch):
    """Added 2026-09-15, by request: a retry (process-level, within this
    function's own loop) must continue the same opencode session rather
    than starting a brand-new one every attempt, but a genuinely fresh
    start (no session_id passed in at all) must not invent one."""
    seen_session_ids = []

    def _fake_run(round_number, extra_message=None, session_id=None):
        seen_session_ids.append(session_id)
        # First attempt has no session yet, discovers "ses_new"; every
        # attempt after that must be handed that same discovered id back.
        return len(seen_session_ids) == 3, "ses_new"

    monkeypatch.setattr(simulate_module, "refresh_knowledge_graph", lambda round_number: None)
    monkeypatch.setattr(simulate_module, "run_norm_implementer", _fake_run)
    monkeypatch.setattr(simulate_module.time, "sleep", lambda s: None)

    # A fresh start: no session_id passed in at all.
    assert simulate_module.run_norm_implementer_with_retry(1) == (True, "ses_new")
    assert seen_session_ids == [None, "ses_new", "ses_new"]


def test_a_caller_supplied_session_id_is_continued_from_the_start(monkeypatch):
    """A repair cycle (a fresh call to run_norm_implementer_with_retry with
    a session_id already known from an earlier phase of the same round)
    must continue that session on its very first attempt too, not just on
    its own internal retries."""
    seen_session_ids = []

    def _fake_run(round_number, extra_message=None, session_id=None):
        seen_session_ids.append(session_id)
        return True, session_id

    monkeypatch.setattr(simulate_module, "refresh_knowledge_graph", lambda round_number: None)
    monkeypatch.setattr(simulate_module, "run_norm_implementer", _fake_run)
    monkeypatch.setattr(simulate_module.time, "sleep", lambda s: None)

    assert simulate_module.run_norm_implementer_with_retry(1, session_id="ses_existing") == (True, "ses_existing")
    assert seen_session_ids == ["ses_existing"]
