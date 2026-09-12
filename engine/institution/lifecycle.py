# LifecycleSpec: the one shared start/duration/expiry/renewal/termination
# shape used by norms (state/config.json), actions (state/actions/*.json),
# roles (state/institution.json), and institutional objects
# (state/objects.json) — a plain dict, stored inline wherever it applies,
# never a separate class instance that would need its own
# serialize/deserialize step. A missing/None lifecycle means "always
# active" — every existing norm/action config predates this field, so
# omitting it is the backward-compatible default, not a special case.
#
# Shape:
#   {"active_from_round": int | None, "duration_rounds": int | None,
#    "expires_at_round": int | None, "renewable": bool,
#    "renewed_count": int, "terminated_round": int | None,
#    "termination_reason": str | None}
# `duration_rounds` and `expires_at_round` are two ways to say the same
# thing (a relative span vs. an absolute round) — set at most one; if both
# are set, `expires_at_round` wins (it's the one is_active()/tick() below
# already resolved duration_rounds into, on a previous tick()).

from dataclasses import dataclass


def default_lifecycle():
    """A fresh, always-active lifecycle — the explicit form of "no
    lifecycle was ever set"."""
    return {
        "active_from_round": None,
        "duration_rounds": None,
        "expires_at_round": None,
        "renewable": True,
        "renewed_count": 0,
        "terminated_round": None,
        "termination_reason": None,
    }


def _resolved_expiry(lifecycle):
    expires_at = lifecycle.get("expires_at_round")
    if expires_at is not None:
        return expires_at
    duration = lifecycle.get("duration_rounds")
    if duration is None:
        return None
    active_from = lifecycle.get("active_from_round") or 0
    return active_from + duration


def is_active(lifecycle, round_number):
    """True if this entry is active during `round_number`. `lifecycle=None`
    (or `{}`) is always active — the backward-compatible default for
    anything that predates this field."""
    if not lifecycle:
        return True
    if lifecycle.get("terminated_round") is not None and round_number >= lifecycle["terminated_round"]:
        return False
    active_from = lifecycle.get("active_from_round") or 0
    if round_number < active_from:
        return False
    expires_at = _resolved_expiry(lifecycle)
    if expires_at is not None and round_number >= expires_at:
        return False
    return True


@dataclass
class LifecycleEvent:
    """Returned by tick() the one round an entry's lifecycle actually
    changes state (expires) — never on any round before or after, so a
    caller can react to it (close a norm_active-style record, emit a
    narration) without re-deriving "did this just happen" itself."""

    kind: str  # "expired"
    round_number: int


def tick(lifecycle, round_number):
    """Call once per round for every lifecycle-bearing entry, before it's
    otherwise used this round. If `duration_rounds`/`expires_at_round` has
    just lapsed, closes the lifecycle in place (sets `terminated_round`/
    `termination_reason`) and returns a LifecycleEvent — exactly once,
    since the very next call sees `terminated_round` already set and
    returns None. A no-op (returns None, mutates nothing) for a lifecycle
    that's absent, not yet expired, or already explicitly terminated."""
    if not lifecycle or lifecycle.get("terminated_round") is not None:
        return None
    expires_at = _resolved_expiry(lifecycle)
    if expires_at is not None and round_number >= expires_at:
        lifecycle["terminated_round"] = expires_at
        lifecycle["termination_reason"] = "duration_elapsed"
        return LifecycleEvent(kind="expired", round_number=expires_at)
    return None


def renew(lifecycle, extra_rounds):
    """Extends an active-or-expired lifecycle by `extra_rounds`, clearing
    any termination tick() already recorded. Raises if `renewable` is
    False — a lifecycle can opt out of ever being renewed."""
    if lifecycle.get("renewable", True) is False:
        raise ValueError("this lifecycle is not renewable")
    lifecycle["terminated_round"] = None
    lifecycle["termination_reason"] = None
    if lifecycle.get("expires_at_round") is not None:
        lifecycle["expires_at_round"] += extra_rounds
    elif lifecycle.get("duration_rounds") is not None:
        lifecycle["duration_rounds"] += extra_rounds
    lifecycle["renewed_count"] = lifecycle.get("renewed_count", 0) + 1
    return lifecycle


def terminate(lifecycle, round_number, reason):
    """Closes a lifecycle immediately, regardless of any duration/expiry it
    had — an explicit repeal, distinct from tick()'s automatic expiry
    (`termination_reason` differs: caller-supplied here, always
    `"duration_elapsed"` there, so a later read can tell the two apart)."""
    lifecycle["terminated_round"] = round_number
    lifecycle["termination_reason"] = reason
    return lifecycle
