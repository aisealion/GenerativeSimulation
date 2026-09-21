import engine.simulate as simulate_module


def test_succeeds_on_first_attempt_no_sleep_no_extra_calls(monkeypatch):
    calls = []
    sleeps = []
    monkeypatch.setattr(
        simulate_module, "run_norm_architect",
        lambda round_number, extra_message=None, session_id=None: (
            calls.append("run") or True, "ses_1", {"requirements": []}
        ),
    )
    monkeypatch.setattr(simulate_module.time, "sleep", lambda s: sleeps.append(s))

    success, report = simulate_module.run_norm_architect_with_retry(1)
    assert success is True
    assert report == {"requirements": []}
    assert calls == ["run"]
    assert sleeps == []


def test_retries_up_to_the_full_budget_with_a_delay_between_each_attempt(monkeypatch):
    attempts = {"n": 0}
    sleeps = []

    def _fake_run(round_number, extra_message=None, session_id=None):
        attempts["n"] += 1
        succeeded = attempts["n"] == simulate_module.MAX_ARCHITECT_PROCESS_ATTEMPTS
        return succeeded, "ses_1", ({"requirements": []} if succeeded else None)

    monkeypatch.setattr(simulate_module, "run_norm_architect", _fake_run)
    monkeypatch.setattr(simulate_module.time, "sleep", lambda s: sleeps.append(s))

    success, report = simulate_module.run_norm_architect_with_retry(1)
    assert success is True
    assert report == {"requirements": []}
    assert attempts["n"] == simulate_module.MAX_ARCHITECT_PROCESS_ATTEMPTS
    # One sleep between each pair of attempts, never after the final
    # (successful) one.
    assert sleeps == [simulate_module.NORM_ENGINEER_RETRY_DELAY_S] * (simulate_module.MAX_ARCHITECT_PROCESS_ATTEMPTS - 1)


def test_returns_false_and_none_report_after_exhausting_every_attempt(monkeypatch):
    attempts = {"n": 0}
    sleeps = []

    def _always_fails(round_number, extra_message=None, session_id=None):
        attempts["n"] += 1
        return False, "ses_1", None

    monkeypatch.setattr(simulate_module, "run_norm_architect", _always_fails)
    monkeypatch.setattr(simulate_module.time, "sleep", lambda s: sleeps.append(s))

    success, report = simulate_module.run_norm_architect_with_retry(1)
    assert success is False
    assert report is None
    assert attempts["n"] == simulate_module.MAX_ARCHITECT_PROCESS_ATTEMPTS
    assert len(sleeps) == simulate_module.MAX_ARCHITECT_PROCESS_ATTEMPTS - 1


def test_the_budget_is_actually_five(monkeypatch):
    """Same value and reasoning as MAX_ENGINEER_PROCESS_ATTEMPTS — nothing
    about a truncated-session process failure is specific to code-writing
    versus design-and-test-writing, so the architect gets the same bounded
    number of real chances before the round is discarded."""
    assert simulate_module.MAX_ARCHITECT_PROCESS_ATTEMPTS == 5


def test_attempts_are_paired_1_2_then_3_4_then_5_alone(monkeypatch):
    """Same paired-session-continuation scheme as
    run_norm_engineer_with_retry() — attempt 2 must continue attempt 1's
    own session, attempt 4 must continue attempt 3's, but attempt 3 must
    NOT continue attempt 2's session (each pair starts fresh)."""
    seen_session_ids = []

    def _fake_run(round_number, extra_message=None, session_id=None):
        seen_session_ids.append(session_id)
        n = len(seen_session_ids)
        # Every attempt "discovers" a session id unique to its own pair,
        # and every attempt fails (forcing the full 5-attempt budget).
        pair_index = (n - 1) // 2
        return False, f"ses_pair_{pair_index}", None

    monkeypatch.setattr(simulate_module, "run_norm_architect", _fake_run)
    monkeypatch.setattr(simulate_module.time, "sleep", lambda s: None)

    success, report = simulate_module.run_norm_architect_with_retry(1)
    assert success is False
    assert report is None
    assert seen_session_ids == [
        None,             # attempt 1: fresh start
        "ses_pair_0",     # attempt 2: continues attempt 1's discovered session
        None,             # attempt 3: fresh again — pair 1 is over
        "ses_pair_1",     # attempt 4: continues attempt 3's discovered session
        None,             # attempt 5: fresh again — pair 2 is over
    ]
