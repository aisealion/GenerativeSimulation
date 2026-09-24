"""Direct unit tests for _render_engineer_repair_preamble() — the shared
repair-message preamble norm-engineer gets on both a compile/validation
error and an auditor NEEDS_REPAIR finding.

2026-09-25: session continuation across a round's repair loop was
narrowed from "the whole loop" to "paired attempts" (1&2 share a session,
3&4 share a new one, ...) after a real round showed an unbounded-within-
the-round session degrading partway through — not crashing, but
increasingly substituting fabricated `[Assistant tool call]: ...` text
for real tool use while still self-reporting success. A pair boundary
(an odd attempt) now starts a genuinely fresh session, so this function's
own `repair_history` — an orchestrator-recorded log, not the model's own
claims — is what carries continuity across that boundary instead."""
from engine.simulate import _render_engineer_repair_preamble, MAX_NORM_REPAIR_ATTEMPTS


def test_fresh_session_is_told_it_has_no_memory():
    text = _render_engineer_repair_preamble(3, 1, "some error", True, [])
    assert "FRESH session" in text
    assert "no memory of any earlier attempt" in text


def test_continued_session_is_told_it_has_real_memory():
    text = _render_engineer_repair_preamble(3, 2, "some error", False, [])
    assert "continues your immediately previous attempt's own session" in text
    assert "real memory of what you just tried" in text


def test_attempt_number_and_budget_are_stated():
    text = _render_engineer_repair_preamble(7, 4, "some error", False, [])
    assert f"repair attempt 4 of {MAX_NORM_REPAIR_ATTEMPTS} for round 7" in text


def test_what_was_found_is_included_verbatim():
    text = _render_engineer_repair_preamble(1, 1, "SPECIFIC_ERROR_MARKER_XYZ", True, [])
    assert "SPECIFIC_ERROR_MARKER_XYZ" in text


def test_repair_history_is_rendered_when_present():
    history = ["attempt 1: compile/validation error — ModuleNotFoundError: no module 'foo'",
               "attempt 2: compile/validation error — same error still"]
    text = _render_engineer_repair_preamble(1, 3, "current error", True, history)
    assert "Previous attempts on this round, in order:" in text
    assert "attempt 1: compile/validation error — ModuleNotFoundError: no module 'foo'" in text
    assert "attempt 2: compile/validation error — same error still" in text


def test_no_history_section_when_history_is_empty():
    text = _render_engineer_repair_preamble(1, 1, "current error", True, [])
    assert "Previous attempts on this round" not in text


def test_asks_to_use_real_tools_not_narrate():
    text = _render_engineer_repair_preamble(1, 1, "some error", True, [])
    assert "never just narrate what a check would" in text
