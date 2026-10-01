"""Direct unit tests for _render_engineer_repair_preamble() — the shared
repair-message preamble norm-engineer gets on both a compile/validation
error and an auditor NEEDS_REPAIR finding.

2026-09-25: session continuation across a round's repair loop was
narrowed from "the whole loop" to "paired attempts" (1&2 share a session,
3&4 share a new one, ...) after a real round showed an unbounded-within-
the-round session degrading partway through — not crashing, but
increasingly substituting fabricated `[Assistant tool call]: ...` text
for real tool use while still self-reporting success.

2026-10-02: pairing itself was removed after a different round showed the
SAME session-growth failure reached within a single pair — one fresh
attempt alone produced 34 near-identical "I have successfully completed"
text turns, and its paired continuation then timed out after 3600s having
produced nothing. Every repair call is now independently fresh (no
`session_is_fresh` parameter any more — this function only ever renders
the fresh-session message); `repair_history` — an orchestrator-recorded
log, not the model's own claims — is what carries continuity across every
attempt instead of session memory.

2026-09-27: compile-class and audit-class repairs draw from separate
budgets (MAX_NORM_COMPILE_REPAIR_ATTEMPTS / MAX_NORM_AUDIT_REPAIR_ATTEMPTS)
after two real rounds showed a round needing several compile-fixes
starving the harder audit-refinement work of its own fair chance under one
shared pool — so this function now takes an explicit `repair_kind` and
`max_attempts` instead of assuming one shared constant."""
from engine.simulate import _render_engineer_repair_preamble


def test_every_attempt_is_told_it_has_no_session_memory():
    text = _render_engineer_repair_preamble(3, "compile", 1, 10, "some error", [])
    assert "FRESH session" in text
    assert "no memory of any earlier attempt" in text
    assert "nothing from your own previous turns carries forward" in text


def test_a_later_attempt_number_is_told_the_same_thing():
    # Not just attempt 1 — there's no pairing left to make a later attempt
    # number special.
    text = _render_engineer_repair_preamble(3, "compile", 4, 10, "some error", [])
    assert "FRESH session" in text


def test_attempt_number_and_budget_are_stated_for_compile_repairs():
    text = _render_engineer_repair_preamble(7, "compile", 4, 10, "some error", [])
    assert "compile/structural repair attempt 4 of 10 for round 7" in text


def test_attempt_number_and_budget_are_stated_for_audit_repairs():
    text = _render_engineer_repair_preamble(7, "audit", 2, 5, "some error", [])
    assert "audit repair attempt 2 of 5 for round 7" in text


def test_what_was_found_is_included_verbatim():
    text = _render_engineer_repair_preamble(1, "compile", 1, 10, "SPECIFIC_ERROR_MARKER_XYZ", [])
    assert "SPECIFIC_ERROR_MARKER_XYZ" in text


def test_repair_history_is_rendered_when_present():
    history = ["attempt 1 (compile): ModuleNotFoundError: no module 'foo'",
               "attempt 2 (compile): same error still"]
    text = _render_engineer_repair_preamble(1, "compile", 3, 10, "current error", history)
    assert "Previous attempts on this round, in order:" in text
    assert "attempt 1 (compile): ModuleNotFoundError: no module 'foo'" in text
    assert "attempt 2 (compile): same error still" in text


def test_no_history_section_when_history_is_empty():
    text = _render_engineer_repair_preamble(1, "compile", 1, 10, "current error", [])
    assert "Previous attempts on this round" not in text


def test_asks_to_use_real_tools_not_narrate():
    text = _render_engineer_repair_preamble(1, "compile", 1, 10, "some error", [])
    assert "never just narrate what a check would" in text


def test_compile_repair_mentions_the_fixed_check_order():
    text = _render_engineer_repair_preamble(1, "compile", 1, 10, "some error", [])
    assert "fixed order (compile/syntax" in text


def test_audit_repair_asks_to_check_for_the_same_pattern_elsewhere_instead():
    text = _render_engineer_repair_preamble(1, "audit", 1, 5, "some error", [])
    assert "fixed order (compile/syntax" not in text
    assert "same weak-evidence pattern exists elsewhere" in text
