"""Locks in the 2026-09-24 fix to extract_last_step_reason() — found from
a real production round: norm-engineer was discarded after exhausting all
5 process-retry attempts, even though 4 of the 5 attempts had actually
produced a complete, well-formed closing report (one of them with
norm_check_tests_pass: true — the round had genuinely succeeded). The old
implementation read the `reason` field off the LAST step_finish event in
the stream; under opencode v2, a session that ends normally on a
text-only final turn apparently never gets its own closing
step_finish/reason:"stop" event, so the old logic always fell back to the
second-to-last (tool-related) step_finish and reported "tool-calls" —
misclassifying every genuinely-complete session as truncated. The fix
looks at the actual last "text" or "tool_use" event's own type directly,
instead of depending on a step_finish event that may never arrive."""
import json

from engine.simulate import extract_last_step_reason


def _line(event_type, **part_fields):
    return json.dumps({"type": event_type, "part": part_fields})


def test_stream_ending_on_a_text_event_is_a_genuine_stop():
    """The exact real-world shape that was broken: tool_use -> its own
    step_finish (reason=tool-calls) -> a final text turn with NO closing
    step_finish after it at all."""
    stdout = "\n".join([
        _line("tool_use", tool="shell"),
        _line("step_finish", reason="tool-calls"),
        _line("text", text="All done. ```json\n{}\n```"),
    ])
    assert extract_last_step_reason(stdout) == "stop"


def test_stream_ending_on_a_tool_use_event_is_still_truncated():
    """The real truncation signature this function exists to catch: the
    session ends right after a tool call, with no follow-up text turn."""
    stdout = "\n".join([
        _line("text", text="Let me check something first."),
        _line("step_finish", reason="tool-calls"),
        _line("tool_use", tool="shell"),
    ])
    assert extract_last_step_reason(stdout) == "tool-calls"


def test_falls_back_to_step_finish_reason_when_no_text_or_tool_use_ever_appears():
    """The original empty/failed-completion signature this function also
    catches: the underlying model completion silently failed or returned
    nothing at all — no text, no tool call, just a step_finish carrying
    whatever reason opencode itself reported."""
    stdout = _line("step_finish", reason="unknown")
    assert extract_last_step_reason(stdout) == "unknown"


def test_empty_stream_returns_none():
    assert extract_last_step_reason("") is None


def test_unparseable_stream_returns_none():
    assert extract_last_step_reason("not json at all") is None


def test_a_realistic_multi_turn_stop_matches_the_real_captured_shape():
    """Mirrors the actual production entry that was misclassified: several
    tool-calling turns, each closed by its own step_finish(tool-calls),
    followed by a final text-only turn with no closing step_finish."""
    stdout = "\n".join([
        _line("tool_use", tool="read"),
        _line("step_finish", reason="tool-calls"),
        _line("tool_use", tool="write"),
        _line("step_finish", reason="tool-calls"),
        _line("text", text="This round is complete and ready for finalization."),
    ])
    assert extract_last_step_reason(stdout) == "stop"
