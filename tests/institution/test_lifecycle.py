import pytest

from engine.institution.lifecycle import (
    default_lifecycle, is_active, tick, renew, terminate, LifecycleEvent,
)


def test_missing_or_default_lifecycle_is_always_active():
    assert is_active(None, 1) is True
    assert is_active({}, 999) is True
    assert is_active(default_lifecycle(), 999) is True


def test_active_from_round_gates_the_start():
    lifecycle = {**default_lifecycle(), "active_from_round": 5}
    assert is_active(lifecycle, 4) is False
    assert is_active(lifecycle, 5) is True
    assert is_active(lifecycle, 100) is True


def test_duration_rounds_expires_relative_to_active_from():
    lifecycle = {**default_lifecycle(), "active_from_round": 10, "duration_rounds": 3}
    assert is_active(lifecycle, 9) is False   # not started yet
    assert is_active(lifecycle, 10) is True
    assert is_active(lifecycle, 12) is True
    assert is_active(lifecycle, 13) is False  # 10 + 3 -> inactive at round 13


def test_duration_rounds_defaults_active_from_to_zero():
    lifecycle = {**default_lifecycle(), "duration_rounds": 5}
    assert is_active(lifecycle, 4) is True
    assert is_active(lifecycle, 5) is False


def test_explicit_expires_at_round_wins_over_duration_rounds():
    lifecycle = {**default_lifecycle(), "duration_rounds": 5, "expires_at_round": 2}
    assert is_active(lifecycle, 1) is True
    assert is_active(lifecycle, 2) is False


def test_terminated_round_ends_it_immediately():
    lifecycle = {**default_lifecycle(), "terminated_round": 3}
    assert is_active(lifecycle, 2) is True
    assert is_active(lifecycle, 3) is False


def test_tick_fires_exactly_once_on_expiry():
    lifecycle = {**default_lifecycle(), "active_from_round": 0, "duration_rounds": 3}

    assert tick(lifecycle, 1) is None
    assert tick(lifecycle, 2) is None

    event = tick(lifecycle, 3)
    assert event == LifecycleEvent(kind="expired", round_number=3)
    assert lifecycle["terminated_round"] == 3
    assert lifecycle["termination_reason"] == "duration_elapsed"

    # Already closed — never fires again, even on a later round.
    assert tick(lifecycle, 3) is None
    assert tick(lifecycle, 4) is None


def test_tick_never_fires_for_an_indefinite_lifecycle():
    lifecycle = default_lifecycle()
    for round_number in range(50):
        assert tick(lifecycle, round_number) is None
    assert lifecycle["terminated_round"] is None


def test_renew_clears_termination_and_extends_duration():
    lifecycle = {**default_lifecycle(), "duration_rounds": 3}
    tick(lifecycle, 3)
    assert lifecycle["terminated_round"] is not None

    renew(lifecycle, extra_rounds=5)

    assert lifecycle["terminated_round"] is None
    assert lifecycle["termination_reason"] is None
    assert lifecycle["duration_rounds"] == 8
    assert lifecycle["renewed_count"] == 1
    assert is_active(lifecycle, 3) is True
    assert is_active(lifecycle, 7) is True
    assert is_active(lifecycle, 8) is False


def test_renew_extends_expires_at_round_when_that_form_was_used():
    lifecycle = {**default_lifecycle(), "expires_at_round": 5}
    renew(lifecycle, extra_rounds=2)
    assert lifecycle["expires_at_round"] == 7


def test_renew_raises_when_not_renewable():
    lifecycle = {**default_lifecycle(), "duration_rounds": 3, "renewable": False}
    with pytest.raises(ValueError, match="not renewable"):
        renew(lifecycle, extra_rounds=1)


def test_terminate_closes_immediately_regardless_of_duration():
    lifecycle = {**default_lifecycle(), "duration_rounds": 100}
    terminate(lifecycle, round_number=4, reason="repealed_by_norm")
    assert lifecycle["terminated_round"] == 4
    assert lifecycle["termination_reason"] == "repealed_by_norm"
    assert is_active(lifecycle, 4) is False
    assert is_active(lifecycle, 3) is True
