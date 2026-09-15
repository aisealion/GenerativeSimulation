#!/usr/bin/env python3
import argparse
import importlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from engine.call_log import log_call
from engine.institution.runtime import ActionRuntime
from engine.institution.scheduler import compile_schedule
from engine.institution.history import diff_institution
from engine.institution.rules import tick_rule_lifecycles, all_configured_rules

try:
    # matplotlib may be missing from a minimal venv; monitoring is optional.
    from engine.monitoring import update_plots
except ImportError as exc:
    print(f"  [monitoring disabled: {exc}]")

    def update_plots(state):
        pass

ROOT = Path(__file__).resolve().parent.parent
# Dedicated per-agent logs, written alongside the shared ops/logs/model_calls.jsonl.
NORM_IMPLEMENTER_LOG_PATH = ROOT / "ops" / "logs" / "norm_implementer.jsonl"
NORM_EVALUATOR_LOG_PATH = ROOT / "ops" / "logs" / "norm_evaluator.jsonl"
COLLAPSE_THRESHOLD_KG = 0
DEFAULT_MAX_ROUNDS = 100

# Everything the norm-implementer is allowed to touch. Staged (git add) by
# stage_norm_implementation() and reverted (git checkout/clean) by
# discard_norm_implementation() on a discard.
NORM_IMPLEMENTER_TRACKED_PATHS = [
    # state/runtime.json is never here — simulation-owned, never the
    # implementer's to write; kept off so a discard's `git clean -fd`
    # can never touch it. state/schedule.json is ALSO never here any
    # more, for the same reason, one level removed: it's now a COMPILED
    # artifact (engine.institution.scheduler.compile_schedule(), rebuilt
    # every round from state/actions/*.json's own scheduling.after/before)
    # rather than something hand-edited — see ROUND_ARTIFACT_PATHS below.
    # "actions" covers both actions/handlers/*.py AND
    # actions/rules/{action_name}/*.py — rule plugins moved under actions/
    # entirely (no more standalone top-level norms/ directory) since a
    # rule is always about one specific action.
    "actions",
    "objects",
    "prompts",
    # Implementer-authored tests for its own rule/action changes.
    "tests/norm_checks",
    # The norm-evaluator's own generated tests — must revert alongside the
    # rule/action code they test if this round is discarded.
    "tests/norm_evaluation",
    "state/config.json",
    "state/fluents.json",
    "state/fluents_schema.md",
    # Point-in-time occurrences (engine.institution.events) — populated by
    # code (ctx.events.emit()), same relationship this list already has
    # with state/fluents.json.
    "state/events.json",
    "state/actions",
    "state/object_types",
    "state/objects.json",
    # state/norm_specs is NOT here — see ROUND_ARTIFACT_PATHS below. A spec
    # must survive a discard as the forensic record of what was analyzed.
    "state/institution.json",
    # Editable so an edit here is actually staged and syntax-checked.
    "engine/simulate.py",
]

# Never touchable by a norm round — fixed physics, the generic institution
# kernel, and the 5 protected actions' own declarative specs/handlers.
# Enforced by a real git-diff check
# (norm_implementation_protected_path_violations()), not just the
# permission.edit YAML, whose "deny + allow" behavior on opencode is
# unverified.
PROTECTED_PATHS = [
    "state/actions/harvest.json",
    "state/actions/propose.json",
    "state/actions/vote.json",
    "state/actions/critique.json",
    # Unimplemented stub, permanently gated off — still off-limits.
    "state/actions/discuss.json",
    "actions/handlers/harvest.py",
    "actions/handlers/propose.py",
    "actions/handlers/vote.py",
    "actions/handlers/critique.py",
    "actions/handlers/discuss.py",
    "engine/institution",
    "engine/physics.py",
    "roles/roles.py",
]

HOLDS_AT_RE = re.compile(r"holdsAt\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)")


def load_state(round_number):
    return {
        "config": json.loads((ROOT / "state" / "config.json").read_text()),
        "fluents": json.loads((ROOT / "state" / "fluents.json").read_text()),
        # Point-in-time occurrences (engine.institution.events) — distinct
        # from fluents.json's own interval facts; see that module's own
        # docstring for why the two are kept apart.
        "events": json.loads((ROOT / "state" / "events.json").read_text()),
        "runtime": json.loads((ROOT / "state" / "runtime.json").read_text()),
        "agents": json.loads((ROOT / "constants" / "agents.json").read_text()),
        # Object TYPE definitions are auto-discovered by scanning
        # state/object_types/*.json directly (keyed by each file's own
        # type_name) — same "the directory itself is the source of truth,
        # institution.json is drift-checked documentation, never the load
        # path" principle actions/rules/*/*.py already uses. Object INSTANCE
        # declarations (id/type only — never mutable field values, see
        # engine/institution/objects.py's own module docstring) come from
        # state/objects.json.
        "object_types": load_object_types(),
        "objects": load_objects(),
        "round_number": round_number,
    }


def load_object_types():
    types = {}
    for path in sorted((ROOT / "state" / "object_types").glob("*.json")):
        spec = json.loads(path.read_text())
        types[spec["type_name"]] = spec
    return types


def load_objects():
    return json.loads((ROOT / "state" / "objects.json").read_text())


def load_action_spec(action_name):
    """state/actions/{action_name}.json — loaded by filename-stem
    convention (action_name == the state/schedule.json key == the spec's
    own "name" field), never indirected through institution.json's own
    "spec" field, which stays purely informational/drift-checked (see
    norm_implementation_institution_errors()) rather than a live load
    path — the same relationship institution.json already has with
    actions/rules/**/*.py and state/object_types/*.json."""
    return json.loads((ROOT / "state" / "actions" / f"{action_name}.json").read_text())


def load_institution():
    return json.loads((ROOT / "state" / "institution.json").read_text())


def load_schedule():
    return json.loads((ROOT / "state" / "schedule.json").read_text())


def compile_and_write_schedule():
    """Regenerates state/schedule.json from state/institution.json's own
    action catalog plus each state/actions/*.json's own
    scheduling.after/before/gate — schedule.json is now a COMPILED
    artifact (engine.institution.scheduler.compile_schedule()), never
    hand-edited, so a norm-implementer round that added or reordered an
    action can never leave it silently out of sync with institution.json
    (a whole bug class the old hand-maintained file had no check for at
    all). Called at the top of every round, and once before main()'s own
    initial read, so this is always fresh before anything reads it."""
    institution = load_institution()
    action_specs = {name: load_action_spec(name) for name in institution.get("actions", {})}
    schedule = compile_schedule(action_specs)
    (ROOT / "state" / "schedule.json").write_text(json.dumps(schedule, indent=2) + "\n")
    return schedule


def evaluate_gate(condition, fluents, round_number):
    """Supported syntax: "true", "false", or "holdsAt(<fluent_name>)" — true
    if any record for that fluent (any holder/args) is currently active."""
    condition = condition.strip()
    if condition == "true":
        return True
    if condition == "false":
        return False

    match = HOLDS_AT_RE.fullmatch(condition)
    if not match:
        raise ValueError(f"unsupported state/schedule.json gate condition: {condition!r}")

    fluent_name = match.group(1)
    return any(
        f["fluent"] == fluent_name
        and f["initiated_round"] <= round_number
        and (f["terminated_round"] is None or f["terminated_round"] > round_number)
        for f in fluents
    )


def save_runtime(state):
    (ROOT / "state" / "runtime.json").write_text(json.dumps(state["runtime"], indent=2) + "\n")


def save_fluents(state):
    (ROOT / "state" / "fluents.json").write_text(json.dumps(state["fluents"], indent=2) + "\n")


def save_events(state):
    (ROOT / "state" / "events.json").write_text(json.dumps(state["events"], indent=2) + "\n")


def write_memory_episodes(action_spec, state, record, round_number):
    """No-ops if the optional Neo4j memory layer isn't configured."""
    if not os.environ.get("NEO4J_URI"):
        return
    try:
        from engine.memory.write import write_episode
        from engine.institution.runtime import resolve_memory_writes

        memory_writes = resolve_memory_writes(action_spec["execution"]["handler"])
        for spec in memory_writes(state, record):
            write_episode(round_num=round_number, **spec)
    except Exception as exc:
        print(f"  [memory write skipped: {exc}]")


def write_fact_memory_events(state, round_number):
    """Like write_memory_episodes() but for fluent-sourced events
    (roles.roles set_fact()/end_fact() narration). Runs once per round,
    after every action, so an early action's fact doesn't also look "new"
    to a later action's own call this same round."""
    if not os.environ.get("NEO4J_URI"):
        return
    try:
        from engine.memory.write import write_episode
        from roles.roles import fact_memory_events

        for spec in fact_memory_events(state["fluents"], round_number):
            write_episode(round_num=round_number, **spec)
    except Exception as exc:
        print(f"  [memory write skipped: {exc}]")


def write_event_memory_episodes(state, round_number):
    """Like write_fact_memory_events() but for engine.institution.events —
    point-in-time occurrences (an object mutation, a one-off announcement)
    rather than a fluent's own open/close narration. Same once-per-round,
    after-every-action timing, for the same reason."""
    if not os.environ.get("NEO4J_URI"):
        return
    try:
        from engine.memory.write import write_episode
        from engine.institution.events import event_memory_specs

        for spec in event_memory_specs(state["events"], round_number):
            write_episode(round_num=round_number, **spec)
    except Exception as exc:
        print(f"  [memory write skipped: {exc}]")


def parse_opencode_jsonl(stdout):
    """Parses opencode run --format json's JSONL stream: counts tool_use
    and step_finish events (a step is one full model turn; not every step
    calls a tool, so this can exceed the tool-call count) and reconstructs
    the final response by joining each distinct messageID's text in the
    order first seen — a long session can span several text events across
    different messages, and keeping only the last one can silently drop an
    earlier message containing the real report. Degrades to (0, 0, stdout)
    on any parse failure rather than raising."""
    tool_calls = 0
    steps = 0
    texts_by_message = {}
    try:
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event.get("type") == "tool_use":
                tool_calls += 1
            elif event.get("type") == "step_finish":
                steps += 1
            elif event.get("type") == "text":
                part = event.get("part", {})
                text = part.get("text")
                if text:
                    texts_by_message[part.get("messageID")] = text
    except (json.JSONDecodeError, AttributeError):
        return 0, 0, stdout
    final_text = "\n\n".join(texts_by_message.values())
    return tool_calls, steps, final_text or stdout


def extract_tool_trace(stdout):
    """Ordered list of {"tool": name} per tool_use event in the same JSONL
    stream parse_opencode_jsonl() reads — feeds ops/logs/norm_implementer.jsonl
    / ops/logs/norm_evaluator.jsonl. A tool named "invalid" means the model
    called a nonexistent tool; `detail` then carries opencode's own
    rejection message. Degrades to [] on any parse failure."""
    trace = []
    try:
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event.get("type") != "tool_use":
                continue
            part = event.get("part", {})
            tool = part.get("tool")
            entry = {"tool": tool}
            if tool == "invalid":
                entry["detail"] = part.get("state", {}).get("input")
            trace.append(entry)
    except (json.JSONDecodeError, AttributeError):
        return []
    return trace


def extract_last_step_reason(stdout):
    """Returns the `reason` field of the LAST step_finish event in the
    stream, or None if none found / on parse failure. A genuine, deliberate
    end of turn always reports "stop". Two other real, confirmed
    truncation signatures found analyzing an actual 12-round run, both
    meaning the session ended before the model was actually done, not
    because it chose to stop: "tool-calls" as the very last event (the
    session ended right after a tool call, with no follow-up turn at all —
    7 of 26 real norm-implementer invocations on that run), and "unknown"
    paired with all-zero token counts (6 of 26) — the underlying model
    completion itself silently failed or returned empty, and opencode
    still exited 0, indistinguishable from a real success by returncode
    alone. See run_norm_implementer()'s use of this."""
    last_reason = None
    try:
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event.get("type") == "step_finish":
                last_reason = event.get("part", {}).get("reason")
    except (json.JSONDecodeError, AttributeError):
        return None
    return last_reason


def extract_session_id(stdout):
    """First sessionID found anywhere in the opencode run --format json
    JSONL stream (every event in one session carries the same id) — used
    to continue the SAME opencode session across a retry
    (run_norm_implementer_with_retry()/implement_and_evaluate_norm()),
    added 2026-09-15 by request, instead of starting a brand-new session
    every single attempt. Returns None on any parse failure or if no
    event carries one — the caller then falls back to starting fresh,
    exactly like today's behavior."""
    try:
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            sid = event.get("sessionID") or event.get("part", {}).get("sessionID")
            if sid:
                return sid
    except (json.JSONDecodeError, AttributeError):
        return None
    return None


def extract_json_report(text, required_keys=()):
    """Pulls the trailing fenced ```json block matching required_keys out of
    an agent's response, scanning from the end backwards so an earlier,
    unrelated example json block never gets mistaken for the real report.
    Returns None if nothing qualifies."""
    matches = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    required_keys = set(required_keys)
    for candidate in reversed(matches):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        if required_keys and not required_keys.issubset(parsed.keys()):
            continue
        return parsed
    return None


EVALUATION_RESULT_RE = re.compile(r"EVALUATION_RESULT:\s*(COMPLIANT|NEEDS_REPAIR)\b", re.IGNORECASE)


def extract_evaluation_result(text):
    """Finds EVALUATION_RESULT: COMPLIANT|NEEDS_REPAIR anywhere in the
    response (case-insensitive, last match wins) — simpler and more
    reliable than requiring a specific JSON shape, which real evaluator
    responses kept failing to reproduce exactly. Returns None if absent."""
    matches = EVALUATION_RESULT_RE.findall(text)
    if not matches:
        return None
    return matches[-1].upper()


def run_norm_implementer(round_number, extra_message=None, session_id=None):
    """Runs the norm-implementer as an opencode subprocess. Returns
    (success, session_id) — success is True on a clean (returncode 0) run
    that also ended on a genuine "stop" (see extract_last_step_reason()),
    False on any failure — a timeout, a crash, a non-zero exit, or a
    session that was silently truncated mid-task despite exiting 0.
    Analyzing a real 12-round run found this last case is common (13 of 26
    real invocations never reached a deliberate stop) and is very likely
    why code-writing specifically (which tends to happen only after
    exploration/spec-writing) so rarely got reached at all — not because
    the implementation itself was too costly to attempt. The caller treats
    a False success like a compile error: discard this round's changes and
    continue, rather than crashing the whole multi-round run or trusting
    partial work as if it were final.

    session_id, when given, is passed to opencode as `--session <id>` so
    this call CONTINUES that existing session instead of starting a fresh
    one — added 2026-09-15 by request, so a retry (process-level or a
    repair cycle) doesn't have to re-derive everything about the round
    from scratch by re-reading files a previous session already read. The
    returned session_id is always the real id opencode actually used
    (extracted from this call's own output, falling back to whatever was
    passed in if extraction fails) — the caller threads it into the next
    call to keep continuing the same session; passing None starts fresh,
    exactly like before this change."""
    print("\n--- invoking norm-implementer ---")
    # State the round number explicitly — the model can't reliably infer it
    # from file contents alone. Also restates the closing-json-block
    # requirement AND the implement-first/spec-last ordering on every
    # invocation, not just on repair — the ordering exists specifically
    # because writing the spec first was the thing repeatedly mistaken for
    # "done" (see norm_implementation_no_code_changes_errors()).
    message = extra_message or (
        f"This is round {round_number}. norm.txt has been updated for this round. "
        f"Read it and implement accordingly, following your standing instructions. "
        f"Implement every requirement FIRST — then, as your LAST step, write your "
        f"institutional design specification (documenting what you actually built) to "
        f"exactly state/norm_specs/round_{round_number}.md "
        f"— use {round_number} for the round number, not a number inferred from any other file. "
        f"Do not stop after writing this file's design in your head without having "
        f"implemented it; do not write the file itself until implementation is done. "
        f"End your response with the fenced ```json report block your instructions describe "
        f"(the one containing a \"classification\" key) — this is required every time, not "
        f"just when something went wrong."
    )
    # --auto: same fix already applied to the build-agent invocations below,
    # now applied here too (2026-09-15) — a real run's own logs showed the
    # norm-implementer hallucinating a slightly-wrong absolute path on a
    # read/edit call (a doubled letter, a typo'd username) often enough to
    # matter; opencode's external_directory permission defaults to "ask",
    # and with nobody present to answer in this headless subprocess it
    # silently auto-denies — the session then ends abnormally mid-tool-call
    # rather than recovering, which is a real share of why a round needs so
    # many process retries. --auto only auto-approves what isn't explicitly
    # denied, so the actual `permission.edit`/`permission.bash`/
    # `permission.read` denies this agent already has (ops/, cache dirs,
    # protected paths, etc.) are unaffected.
    cmd = ["opencode", "run", "--agent", "norm-implementer", "--format", "json", "--auto"]
    # --session: continue an existing session instead of starting fresh —
    # only when the caller actually has one (a retry); a genuinely fresh
    # start (session_id=None) omits this entirely, exactly like before.
    if session_id:
        cmd += ["--session", session_id]
    # NORM_IMPLEMENTER_MODEL takes precedence over OPENCODE_MODEL, which is
    # shared with the Understand-Anything build-agent calls below.
    model = os.environ.get("NORM_IMPLEMENTER_MODEL") or os.environ.get("OPENCODE_MODEL")
    if model:
        cmd += ["--model", model]
    cmd.append(message)

    # Generous but bounded — a timeout here is caught, not fatal.
    start = time.monotonic()
    try:
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired as e:
        duration_s = time.monotonic() - start
        # A killed process may still have emitted real JSONL before the
        # timeout — subprocess.run() attaches whatever was captured to the
        # exception, so try to recover the session id from it rather than
        # unconditionally losing track of a session that did get created.
        timeout_session_id = extract_session_id(getattr(e, "stdout", None) or "") or session_id
        print(f"Round {round_number}: norm-implementer didn't finish within 3600s — "
              f"treating this round's norm implementation as failed, not crashing the run.",
              file=sys.stderr)
        log_call(
            also_log_to=NORM_IMPLEMENTER_LOG_PATH,
            call="norm_implementer", agent_id=None, round=round_number, action=None,
            model=model, duration_s=round(duration_s, 3), returncode=None,
            prompt=message, raw_response=None, parsed_response=None,
            tool_call_count=None, step_count=None, tool_call_trace=None,
            last_step_reason=None, session_id=timeout_session_id,
            report=None, error="timeout after 3600s",
        )
        return False, timeout_session_id

    duration_s = time.monotonic() - start
    tool_call_count, step_count, final_text = parse_opencode_jsonl(result.stdout)
    tool_call_trace = extract_tool_trace(result.stdout)
    last_step_reason = extract_last_step_reason(result.stdout)
    report = extract_json_report(final_text, required_keys={"classification"})
    # The real id opencode used this call — falls back to whatever was
    # passed in if this call's own output doesn't parse for some reason,
    # so a retry never regresses to "no session" just because extraction
    # failed once.
    new_session_id = extract_session_id(result.stdout) or session_id

    # A session that ended abnormally (see extract_last_step_reason()'s own
    # docstring for the two real truncation signatures this catches) is not
    # trustworthy even though opencode itself exited 0 — the model was cut
    # off mid-task, not finished. Checked here, not just logged, since a
    # returncode-0 check alone can't tell the two apart.
    truncated = result.returncode == 0 and last_step_reason not in (None, "stop")

    log_call(
        also_log_to=NORM_IMPLEMENTER_LOG_PATH,
        call="norm_implementer",
        agent_id=None,
        round=round_number,
        action=None,
        model=model,
        duration_s=round(duration_s, 3),
        returncode=result.returncode,
        prompt=message,
        raw_response=result.stdout,
        parsed_response=None,
        tool_call_count=tool_call_count,
        step_count=step_count,
        tool_call_trace=tool_call_trace,
        last_step_reason=last_step_reason,
        session_id=new_session_id,
        report=report,
        error=(
            result.stderr.strip() if result.returncode != 0
            else f"session ended abnormally (last step reason: {last_step_reason!r}, not 'stop')"
            if truncated else None
        ),
    )

    print(final_text)
    if result.returncode != 0:
        print(f"Round {round_number}: norm-implementer exited with code {result.returncode} — "
              f"treating this round's norm implementation as failed, not crashing the run.",
              file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return False, new_session_id
    if truncated:
        print(f"Round {round_number}: norm-implementer's session ended abnormally (last step "
              f"reason: {last_step_reason!r}, not a genuine 'stop') — likely a failed or "
              f"truncated completion call, not a deliberate finish. Treating this round's "
              f"partial work as failed rather than trusting it.", file=sys.stderr)
        return False, new_session_id
    return True, new_session_id


def run_norm_evaluator(round_number, extra_message=None, session_id=None):
    """Mirrors run_norm_implementer()'s subprocess/timeout/logging shape,
    against the norm-evaluator agent. Returns (evaluation, session_id):
    evaluation is {"result": "COMPLIANT" | "NEEDS_REPAIR", "text":
    final_text} on a completed run whose response contains a trusted
    sentinel line (see extract_evaluation_result() and the zero-tool-call
    check below), or None on any failure — treated by the caller like a
    norm-implementer failure: discard, don't crash the rest of the run.

    session_id, when given, continues that existing opencode session
    (--session <id>) instead of starting fresh — added 2026-09-15 by
    request, same reasoning as run_norm_implementer()'s own copy of this.
    The returned session_id is always returned (even when evaluation is
    None) so a retry of the evaluator's own process can still continue the
    same session it just failed on, rather than losing track of it."""
    print("\n--- invoking norm-evaluator ---")
    # Restates the sentinel-line requirement on every invocation, not just
    # on retry — the first attempt was the one failing to include it.
    message = extra_message or (
        f"Round {round_number}'s norm-implementer changes are ready to check. Read "
        f"state/norm_specs/round_{round_number}.md and the diff, write and run your own "
        "tests, and report your verdicts following your standing instructions. End your "
        "response with the required EVALUATION_RESULT: COMPLIANT or "
        "EVALUATION_RESULT: NEEDS_REPAIR line — every time, not just when something failed."
    )
    # --auto: same reasoning as run_norm_implementer()'s own copy of this
    # comment (2026-09-15) — a real run showed 4 of 5 evaluator attempts in
    # one round hitting the identical hallucinated-path/external_directory
    # auto-deny, ending abnormally before ever writing a real verdict.
    cmd = ["opencode", "run", "--agent", "norm-evaluator", "--format", "json", "--auto"]
    if session_id:
        cmd += ["--session", session_id]
    # Same fallback as run_norm_implementer() — no reason yet to route this
    # agent to a different model than the implementer it's paired with.
    model = os.environ.get("NORM_IMPLEMENTER_MODEL") or os.environ.get("OPENCODE_MODEL")
    if model:
        cmd += ["--model", model]
    cmd.append(message)

    start = time.monotonic()
    try:
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired as e:
        duration_s = time.monotonic() - start
        timeout_session_id = extract_session_id(getattr(e, "stdout", None) or "") or session_id
        print(f"Round {round_number}: norm-evaluator didn't finish within 1800s — "
              f"treating this evaluation as failed, not crashing the run.", file=sys.stderr)
        log_call(
            also_log_to=NORM_EVALUATOR_LOG_PATH,
            call="norm_evaluator", agent_id=None, round=round_number, action=None,
            model=model, duration_s=round(duration_s, 3), returncode=None,
            prompt=message, raw_response=None, parsed_response=None,
            tool_call_count=None, step_count=None, tool_call_trace=None,
            session_id=timeout_session_id,
            report=None, error="timeout after 1800s",
        )
        return None, timeout_session_id

    duration_s = time.monotonic() - start
    tool_call_count, step_count, final_text = parse_opencode_jsonl(result.stdout)
    tool_call_trace = extract_tool_trace(result.stdout)
    verdict = extract_evaluation_result(final_text)
    new_session_id = extract_session_id(result.stdout) or session_id

    # Reject a verdict reached with zero tool calls — no read/test actually
    # happened that attempt, regardless of how confident the text sounds.
    zero_tool_call_reject = verdict is not None and tool_call_count == 0
    if zero_tool_call_reject:
        print(f"Round {round_number}: norm-evaluator reached a verdict ({verdict}) with zero "
              f"tool calls — no read/test was actually performed, so this verdict is not "
              f"trusted.", file=sys.stderr)

    log_call(
        also_log_to=NORM_EVALUATOR_LOG_PATH,
        call="norm_evaluator",
        agent_id=None,
        round=round_number,
        action=None,
        model=model,
        duration_s=round(duration_s, 3),
        returncode=result.returncode,
        prompt=message,
        raw_response=result.stdout,
        parsed_response=None,
        tool_call_count=tool_call_count,
        step_count=step_count,
        tool_call_trace=tool_call_trace,
        session_id=new_session_id,
        # Just the extracted one-word decision, not the full text (already
        # in raw_response). Reflects the rejection above.
        report=(
            {"result": verdict, "rejected_zero_tool_calls": True} if zero_tool_call_reject
            else ({"result": verdict} if verdict else None)
        ),
        error=None if result.returncode == 0 else result.stderr.strip(),
    )

    print(final_text)
    if result.returncode != 0:
        print(f"Round {round_number}: norm-evaluator exited with code {result.returncode} — "
              f"treating this evaluation as failed, not crashing the run.", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return None, new_session_id
    if verdict is None:
        print(f"Round {round_number}: norm-evaluator's response never contained an "
              f"EVALUATION_RESULT: line — treating this evaluation as failed.", file=sys.stderr)
        return None, new_session_id
    if zero_tool_call_reject:
        return None, new_session_id
    return {"result": verdict, "text": final_text}, new_session_id


def norm_already_committed(round_number):
    result = subprocess.run(
        ["git", "log", "--grep", f"^Round {round_number} norm:", "--oneline"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())


def find_adopted_norm(runtime, round_number):
    """Re-derive the winning proposal from history rather than requiring
    state['adopted_norm'] to have just been set — needed when resuming a
    round where vote already ran in a prior crashed attempt."""
    vote_record = next(
        (r for r in runtime["rounds"] if r["round"] == round_number and r["action"] == "vote"), None
    )
    if vote_record is None:
        return None
    propose_record = next(
        (r for r in runtime["rounds"] if r["round"] == round_number and r["action"] == "propose"), None
    )
    return propose_record["proposals"][vote_record["winning_proposer"]]


def norm_implementation_compile_errors():
    # Syntax-checks every touched .py file, validates every touched .json
    # file, and confirms every rule "type" referenced in
    # state/config.json's "rules" (for every action, not just harvest)
    # resolves to a real registered class (checked in a fresh subprocess
    # so a stale in-process discovery cache can't hide a type just added).
    errors = []
    py_files = set()
    json_files = set()
    for tracked in NORM_IMPLEMENTER_TRACKED_PATHS:
        path = ROOT / tracked
        if path.is_dir():
            py_files.update(path.rglob("*.py"))
            json_files.update(path.rglob("*.json"))
        elif path.suffix == ".py" and path.is_file():
            py_files.add(path)
        elif path.suffix == ".json" and path.is_file():
            json_files.add(path)
    for py_file in sorted(py_files):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(py_file)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            errors.append(f"{py_file.relative_to(ROOT)}:\n{result.stderr.strip()}")
    for json_file in sorted(json_files):
        try:
            json.loads(json_file.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"{json_file.relative_to(ROOT)}:\n{exc}")

    config_path = ROOT / "state" / "config.json"
    if config_path.is_file() and not any(f.startswith("state/config.json") for f in errors):
        check = subprocess.run(
            [sys.executable, "-c", (
                "import json, sys\n"
                "sys.path.insert(0, '.')\n"
                "from engine.institution.rules import RuleSet\n"
                "config = json.loads(open('state/config.json').read())\n"
                "for action_name in config.get('rules', {}):\n"
                "    RuleSet.for_action(config, action_name)\n"
            )],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if check.returncode != 0:
            errors.append(f"state/config.json (rule type check):\n{check.stderr.strip()}")
    return errors


def norm_implementation_runtime_errors():
    # Actually runs the harvest action through the new declarative
    # ActionContext/ActionRuntime (no real LLM call, monkeypatched fisher
    # response) — once using whatever config.json currently activates,
    # then once per registered rule type standalone with generic params,
    # for EVERY action's own actions/rules/{action}/ directory (not just
    # harvest's) — so a type that's never wired into config still gets
    # exercised, no matter which action it's meant to attach to. Also
    # structurally validates every new state/actions/*.json spec (its
    # execution.handler must resolve) and every state/object_types/*.json
    # type (its optional custom_handler, if any, must resolve). Run in a
    # fresh subprocess since this happens mid-round, before
    # reload_project_modules() would next pick up whatever this round just
    # changed on disk.
    script = (
        "import sys, json, os\n"
        "sys.path.insert(0, '.')\n"
        "import engine.llm_agents as llm_agents_module\n"
        "from engine.institution.context import ActionContext\n"
        "from engine.institution.runtime import resolve_handler\n"
        "from engine.institution.rules import discover_rule_types\n"
        "import actions.handlers.harvest as harvest_handler\n"
        "\n"
        "def _fake_call_fisher_agent(agent_id, round_number, action_name, **fields):\n"
        "    return {'effort': 0.5, 'reasoning': 'orchestrator smoke test'}\n"
        "llm_agents_module.call_fisher_agent = _fake_call_fisher_agent\n"
        "\n"
        "config = json.loads(open('state/config.json').read())\n"
        "state = {\n"
        "    'config': config,\n"
        "    'fluents': [],\n"
        "    'runtime': {'stock_kg': 300.0, 'rounds': []},\n"
        "    'agents': {\n"
        "        'agent_0': {'name': 'Smoke0', 'personality_traits': ''},\n"
        "        'agent_1': {'name': 'Smoke1', 'personality_traits': ''},\n"
        "    },\n"
        "    'object_types': {},\n"
        "    'objects': [],\n"
        "    'round_number': 1,\n"
        "}\n"
        "ctx = ActionContext.build({'name': 'harvest'}, state, 1)\n"
        "harvest_handler.run(ctx)\n"
        "\n"
        "smoke_state = {\n"
        "    'config': {}, 'fluents': [], 'runtime': {'stock_kg': 200.0, 'rounds': [], 'objects': {}},\n"
        "    'agents': {}, 'object_types': {}, 'objects': [], 'round_number': 1,\n"
        "}\n"
        "errors = []\n"
        "for action_name in sorted(os.listdir('actions/rules')) if os.path.isdir('actions/rules') else []:\n"
        "    action_rules_dir = f'actions/rules/{action_name}'\n"
        "    if not os.path.isdir(action_rules_dir) or action_name == '__pycache__':\n"
        "        continue\n"
        "    smoke_ctx = ActionContext.build({'name': action_name}, smoke_state, 1)\n"
        "    for type_name, cls in sorted(discover_rule_types(action_name).items()):\n"
        "        try:\n"
        "            rule = cls(key=type_name, params={})\n"
        "            rule.before_round(smoke_state, 1)\n"
        "            rule.before_action(smoke_ctx)\n"
        "            rule.is_eligible(smoke_ctx, 'agent_0')\n"
        "            rule.describe(smoke_ctx, 'agent_0')\n"
        "            record_entry = {'harvested_kg': 20.0, 'effort': 0.5, 'participated': True, 'note': None}\n"
        "            rule.after_agent(smoke_ctx, 'agent_0', record_entry)\n"
        "            rule.after_action(smoke_ctx, {'agents': {'agent_0': record_entry}})\n"
        "            rule.after_round(smoke_state, 1)\n"
        "        except Exception as exc:\n"
        "            errors.append(f'actions/rules/{action_name}/ ({type_name}): {type(exc).__name__}: {exc}')\n"
        "\n"
        "protected_action_names = {'harvest', 'propose', 'critique', 'vote', 'discuss'}\n"
        "institution = json.loads(open('state/institution.json').read())\n"
        "for json_file in sorted(os.listdir('state/actions')):\n"
        "    if not json_file.endswith('.json'):\n"
        "        continue\n"
        "    stem = json_file[:-len('.json')]\n"
        "    if stem in protected_action_names:\n"
        "        continue\n"
        "    try:\n"
        "        spec = json.loads(open(f'state/actions/{json_file}').read())\n"
        "        if spec.get('name') != stem:\n"
        "            raise ValueError(\n"
        "                f\"state/actions/{json_file}'s name is {spec.get('name')!r}, \"\n"
        "                f'must match the filename stem {stem!r}'\n"
        "            )\n"
        "        if stem not in institution.get('actions', {}):\n"
        "            raise ValueError(f'state/actions/{json_file} exists but has no state/institution.json entry')\n"
        "        resolve_handler(spec['execution']['handler'])\n"
        "    except Exception as exc:\n"
        "        errors.append(f'state/actions/{json_file}: {type(exc).__name__}: {exc}')\n"
        "\n"
        "object_types_dir = 'state/object_types'\n"
        "if os.path.isdir(object_types_dir):\n"
        "    for json_file in sorted(os.listdir(object_types_dir)):\n"
        "        if not json_file.endswith('.json'):\n"
        "            continue\n"
        "        try:\n"
        "            spec = json.loads(open(f'{object_types_dir}/{json_file}').read())\n"
        "            if not spec.get('type_name'):\n"
        "                raise ValueError('missing type_name')\n"
        "            custom_handler = spec.get('custom_handler')\n"
        "            if custom_handler:\n"
        "                import objects.handlers as handlers_package\n"
        "                from engine.institution.registry import discover_handlers\n"
        "                if custom_handler not in discover_handlers(handlers_package):\n"
        "                    raise ValueError(\n"
        "                        f'custom_handler {custom_handler!r} not found under objects/handlers/'\n"
        "                    )\n"
        "        except Exception as exc:\n"
        "            errors.append(f'state/object_types/{json_file}: {type(exc).__name__}: {exc}')\n"
        "\n"
        "if errors:\n"
        "    print('\\n'.join(errors))\n"
        "    sys.exit(1)\n"
    )
    check = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if check.returncode != 0:
        detail = check.stdout.strip() or check.stderr.strip()
        return (
            "Institution runtime check (active config + every registered rule type, for "
            "every action's own actions/rules/ directory + every new state/actions/*.json "
            "spec's execution.handler + every state/object_types/*.json type's "
            f"custom_handler, if any):\n{detail}"
        )
    return None


def _actions_protected_as_of_head():
    """Every action's own spec file, and its handler file (if it names one
    that isn't a builtin), as of HEAD (before this round's own edits) —
    dynamically extends PROTECTED_PATHS so "additive only" covers every
    action any round has ever created, not just the original fixed set.
    Returns [] if institution.json doesn't exist at HEAD or fails to
    parse. Including a builtin handler's own (nonexistent) derived path is
    harmless — `git diff` against a pathspec that never existed at either
    end of the diff simply reports nothing for it."""
    result = subprocess.run(
        ["git", "show", "HEAD:state/institution.json"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    try:
        institution = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    protected = []
    for name, entry in institution.get("actions", {}).items():
        spec_path = entry.get("spec") or f"state/actions/{name}.json"
        protected.append(spec_path)
        spec_result = subprocess.run(
            ["git", "show", f"HEAD:{spec_path}"], cwd=ROOT, capture_output=True, text=True,
        )
        if spec_result.returncode != 0:
            continue
        try:
            spec = json.loads(spec_result.stdout)
        except json.JSONDecodeError:
            continue
        handler = spec.get("execution", {}).get("handler")
        if handler:
            protected.append(f"actions/handlers/{handler}.py")
    return protected


def norm_implementation_protected_path_violations():
    """Hard-fail if this round touched anything in PROTECTED_PATHS or an
    action an earlier round already created (see
    _actions_protected_as_of_head()) — the actual enforcement of
    "additive-only" institutional change, independent of whatever
    opencode's own permission YAML does or doesn't block."""
    protected = PROTECTED_PATHS + _actions_protected_as_of_head()
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--"] + protected,
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    touched = result.stdout.strip()
    if not touched:
        return []
    return [f"norm-implementer touched protected path(s), never allowed:\n{touched}"]


def norm_implementation_institution_errors():
    """Drift check between state/institution.json and reality: an action or
    object type on disk with no institution.json entry, or vice versa, or
    a rule_types/object_types entry whose owner file doesn't exist — any
    of these means institution.json can no longer be trusted as "the
    current institution" for next round's understanding step.

    Does NOT check that a declared action has a state/schedule.json entry
    — that's now structurally guaranteed by construction
    (compile_and_write_schedule() builds schedule.json directly from this
    same institution.json["actions"] dict, so there's no longer a way for
    the two to disagree)."""
    institution_path = ROOT / "state" / "institution.json"
    if not institution_path.is_file():
        return ["state/institution.json is missing"]
    try:
        institution = json.loads(institution_path.read_text())
    except json.JSONDecodeError:
        return []  # already reported by norm_implementation_compile_errors()'s generic JSON check

    protected_action_names = {"harvest", "propose", "critique", "vote", "discuss"}
    on_disk_actions = {
        p.stem for p in (ROOT / "state" / "actions").glob("*.json")
        if p.stem not in protected_action_names
    }
    declared_actions = {
        name for name, entry in institution.get("actions", {}).items()
        if not entry.get("protected")
    }

    errors = []
    for name in sorted(on_disk_actions - declared_actions):
        errors.append(f"state/actions/{name}.json exists but has no state/institution.json entry")
    for name in sorted(declared_actions - on_disk_actions):
        errors.append(f"state/institution.json lists action {name!r} but state/actions/{name}.json doesn't exist")

    # Same symmetric drift check for object types.
    object_types_dir = ROOT / "state" / "object_types"
    on_disk_object_types = (
        {p.stem for p in object_types_dir.glob("*.json")} if object_types_dir.is_dir() else set()
    )
    declared_object_types = set(institution.get("object_types", {}))
    for name in sorted(on_disk_object_types - declared_object_types):
        errors.append(f"state/object_types/{name}.json exists but has no state/institution.json entry")
    for name in sorted(declared_object_types - on_disk_object_types):
        errors.append(f"state/institution.json lists object type {name!r} but state/object_types/{name}.json doesn't exist")

    # Every registered role needs a matching prompts/role_directives/*.md
    # file — engine.llm_agents.render_role_directives() renders every
    # role_directives/{role}.md whose role a given agent currently holds
    # (generalized from what used to be a hardcoded fisher.md-only read;
    # see that function's own docstring). A role registered here with no
    # directive file would raise FileNotFoundError the first round anyone
    # actually holds it, deep inside a real fisher call — catch it before
    # commit instead.
    for role_name in institution.get("roles", {}):
        if not (ROOT / "prompts" / "role_directives" / f"{role_name}.md").is_file():
            errors.append(
                f"state/institution.json declares role {role_name!r} but "
                f"prompts/role_directives/{role_name}.md doesn't exist"
            )

    # Same drift-check pattern for rule_types/object_types: only checks
    # path existence, not that the file's own type_name matches — that
    # stronger check is norm_implementation_orphaned_norm_errors() below
    # (rule_types only, for now — see CLAUDE.md-equivalent notes on
    # object-type orphan checking being deferred).
    for catalog_key in ("rule_types", "object_types"):
        for name, entry in institution.get(catalog_key, {}).items():
            owner = entry.get("owner")
            if owner and not (ROOT / owner).is_file():
                errors.append(
                    f"state/institution.json {catalog_key}[{name!r}] names owner "
                    f"{owner!r} but that file doesn't exist"
                )
    return errors


def norm_implementation_orphaned_norm_errors():
    """Catches a norm-implementer round that creates a new
    actions/rules/{action_name}/{name}.py plugin (a real,
    correctly-written Rule subclass) without adding its type_name to
    state["config"]["rules"][action_name] — the class compiles and passes
    every other check, but RuleSet.for_action() never loads it, so it
    silently never runs. Only checks files this round actually touched
    (an existing, deliberately unreferenced plugin from an earlier round
    is not an error).

    Uses `git status --porcelain`, not `git diff --name-only HEAD` — a
    brand-new file is untracked at this point in the pipeline, and `git
    diff` never shows untracked files."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "actions/rules"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    touched = [
        line[3:] for line in result.stdout.splitlines()
        if line[3:].endswith(".py") and not line[3:].endswith("__init__.py")
    ]
    if not touched:
        return []

    config_path = ROOT / "state" / "config.json"
    if not config_path.is_file():
        return []  # already reported by norm_implementation_compile_errors()
    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError:
        return []  # already reported by norm_implementation_compile_errors()
    active_types_by_action = {
        action_name: {spec.get("type") for spec in specs}
        for action_name, specs in config.get("rules", {}).items()
    }

    # Re-discover fresh in a subprocess — this runs before
    # reload_project_modules() would pick up what this round just wrote.
    # module_path -> (action_name, [type_names]), grouped by the action
    # each touched file's own rule directory belongs to (parsed from
    # actions/rules/{action_name}/... rather than assumed).
    script = (
        "import sys, json, os\n"
        "sys.path.insert(0, '.')\n"
        "from engine.institution.rules import discover_rule_types\n"
        "touched = json.loads(sys.argv[1])\n"
        "action_names = sorted(os.listdir('actions/rules')) if os.path.isdir('actions/rules') else []\n"
        "out = {}\n"
        "for action_name in action_names:\n"
        "    if not os.path.isdir(f'actions/rules/{action_name}') or action_name == '__pycache__':\n"
        "        continue\n"
        "    for type_name, cls in discover_rule_types(action_name).items():\n"
        "        module_path = cls.__module__.replace('.', '/') + '.py'\n"
        "        if module_path in touched:\n"
        "            out.setdefault(module_path, [action_name, []])[1].append(type_name)\n"
        "print(json.dumps(out))\n"
    )
    check = subprocess.run(
        [sys.executable, "-c", script, json.dumps(touched)],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    if check.returncode != 0:
        detail = check.stdout.strip() or check.stderr.strip()
        return [f"rule-type discovery for orphan check failed:\n{detail}"]
    try:
        types_by_file = json.loads(check.stdout.strip())
    except json.JSONDecodeError:
        return []  # discovery itself is exercised separately by the runtime check

    errors = []
    for module_path, (action_name, type_names) in sorted(types_by_file.items()):
        active_types = active_types_by_action.get(action_name, set())
        if not any(t in active_types for t in type_names):
            errors.append(
                f"{module_path} defines type_name(s) {type_names} but none of them "
                f'appear in state["config"]["rules"][{action_name!r}] — this rule will '
                f"never actually run in the simulation until one is added there. "
                f'Add {{"type": "{type_names[0]}", ...}} (with whatever params it '
                f'needs) to state/config.json\'s "rules"[{action_name!r}] list, or '
                f"remove the file if it was never meant to be active yet."
            )
    return errors


def norm_implementation_missing_spec_errors(round_number):
    """Requires state/norm_specs/round_{N}.md to exist and be non-trivial
    before evaluation — catches a round that burns its whole step budget
    on exploration (or hallucinated tool calls) and writes nothing at all.
    Also means the evaluator is never invoked against a round with no
    ground-truth spec to check against.

    Also checks for a specific, recurring real mistake: the model dropping
    the "state/" prefix and writing to norm_specs/round_N.md at the repo
    root instead — confirmed across three separate real rounds (two
    implementer writes, one evaluator read). A generic "file is missing"
    message left the model guessing (one evaluator spiraled through
    several unrelated tool calls before giving up); naming the exact wrong
    path found is far more actionable than restating the correct one
    again, which the per-invocation message already does verbatim."""
    spec_path = ROOT / "state" / "norm_specs" / f"round_{round_number}.md"
    if not spec_path.is_file():
        wrong_path = ROOT / "norm_specs" / f"round_{round_number}.md"
        if wrong_path.is_file():
            return [
                f"You wrote round_{round_number}.md to norm_specs/ (repo root) instead of "
                f"state/norm_specs/ — move it to exactly state/norm_specs/round_{round_number}.md. "
                "This is a path mistake, not a missing spec: the content likely already exists, "
                "it's just in the wrong directory."
            ]
        return [
            f"state/norm_specs/round_{round_number}.md does not exist — the institutional "
            "design specification, documenting what you actually implemented, must be "
            "written to exactly this path as your LAST step, after implementation, "
            "before this round can be evaluated. If you haven't implemented anything "
            "yet, do that first; if you have, write this file now."
        ]
    if len(spec_path.read_text().strip()) < 200:
        return [
            f"state/norm_specs/round_{round_number}.md exists but is too short to be a "
            "real per-requirement specification — write the full spec, not a placeholder."
        ]
    return []


def norm_implementation_unverified_requirements_errors(round_number):
    """norm-finalizer already independently re-checks every claimed `owner`
    file/test before writing state/norm_specs/round_{N}.md, and records
    what it actually found (not what the norm-implementer merely claimed)
    in that same file's own trailing json block, as
    "verification_failures" — but until this check, nothing in the
    orchestrator ever read that field. A round could finish finalization
    with real, named verification failures and still proceed to
    evaluation/commit as if everything were confirmed, since the
    finalizer's own separate closing report (the one containing this same
    list) only ever reaches the norm-implementer's own session, never the
    orchestrator. Added 2026-09-15, found while auditing the self-check
    family for exactly this kind of already-computed-but-unused signal."""
    spec_path = ROOT / "state" / "norm_specs" / f"round_{round_number}.md"
    if not spec_path.is_file():
        return []  # norm_implementation_missing_spec_errors() already reports this
    report = extract_json_report(spec_path.read_text(), required_keys={"verification_failures"})
    if report is None:
        return []  # no verification_failures field to check — not this function's job
    failures = report.get("verification_failures") or []
    if not failures:
        return []
    return [
        f"norm-finalizer's own verification of state/norm_specs/round_{round_number}.md "
        "found requirement(s) whose claimed owner file or test did not actually hold up:\n"
        + "\n".join(f"- {failure}" for failure in failures)
    ]


def norm_implementation_no_code_changes_errors():
    """Catches a real, repeatedly-observed failure distinct from a missing
    spec: the norm-implementer produces a closing report claiming success
    while making zero actual code/config/fluent changes — one real round's
    own closing report was literally {"classification": "success",
    "message": "Round 8 norm specification written..."}, nothing else, not
    even the documented report schema. norm-implementer.md now instructs
    writing state/norm_specs/round_{N}.md *last*, after implementation, for
    exactly this reason (a polished-looking spec written first was the
    thing the model kept mistaking for "done") — but that's a prompt-level
    instruction, not a technical guarantee, so this check still exists as
    the backstop regardless of whether the round even got as far as writing
    a spec. Checked here mechanically via git status against
    NORM_IMPLEMENTER_TRACKED_PATHS (state/norm_specs is deliberately not on
    that list, so a spec-only round — or a round that wrote nothing at
    all — leaves nothing there to see) — never by trusting the model's own
    self-reported classification, which doesn't reliably match the real
    schema anyway.

    Same known blind spot as everywhere else this exact path list is used
    for a "did the implementer do something" check: state/fluents.json can
    be dirtied by ordinary harvest physics (an agent dying) independent of
    any implementer action, so a round that coincides with a death and
    changes nothing else would slip past this. Accepted deliberately, by
    the same standing decision already made for stage_norm_implementation()
    — not re-litigated here."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--"] + NORM_IMPLEMENTER_TRACKED_PATHS,
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    if result.stdout.strip():
        return []
    return [
        "You made zero actual code/config/fluent changes this round — "
        "actions/rules/**/*.py, actions/*.py, state/config.json, state/fluents.json, "
        "and state/institution.json are all untouched. Your own instructions ask you "
        "to implement every requirement FIRST and write state/norm_specs/round_{N}.md "
        "LAST, as a report of what you actually built — so either you stopped before "
        "implementing anything, or you wrote the spec without building what it "
        "describes. Go back and implement every requirement in your design now, in "
        "this same response, then write (or rewrite) the spec to match what's "
        "actually on disk. A closing report claiming success with no files touched is "
        "not a legitimate success."
    ]


def discard_norm_implementation(round_number, errors):
    """Rolls back everything the norm-implementer touched this round —
    `errors` states the actual reason (a compile/syntax failure, a
    protected-path violation, an institution.json drift mismatch, a
    process failure/timeout, or unresolved evaluator findings after
    repairs run out), printed and logged verbatim rather than a generic
    header."""
    print(f"\nRound {round_number}: discarding this round's norm-implementer changes —", file=sys.stderr)
    print("continuing with the previous round's mechanics unchanged. Reason(s):", file=sys.stderr)
    for error in errors:
        print(f"  {error}", file=sys.stderr)

    # Durable, unlike stderr (gitignored slurm-*.err) — the reason for a
    # discard must survive in git history.
    log_call(
        call="norm_implementer_discarded",
        agent_id=None,
        round=round_number,
        action=None,
        model=None,
        duration_s=None,
        returncode=None,
        prompt=None,
        raw_response=None,
        parsed_response=None,
        error="\n\n".join(errors),
    )

    # `git checkout -- <paths>` fails atomically (reverts nothing at all) if
    # even one pathspec doesn't exist in HEAD yet — so only pass it paths
    # that actually exist there. `git clean -fd` already handles a
    # brand-new untracked path on its own.
    existing_paths = [
        p for p in NORM_IMPLEMENTER_TRACKED_PATHS
        if subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{p}"], cwd=ROOT, capture_output=True
        ).returncode == 0
    ]
    if existing_paths:
        subprocess.run(
            ["git", "checkout", "--"] + existing_paths,
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
    subprocess.run(
        ["git", "clean", "-fd", "--"] + NORM_IMPLEMENTER_TRACKED_PATHS,
        cwd=ROOT, check=True, capture_output=True, text=True,
    )


def _norm_activation_summary():
    """Purely informational (never gates anything) — printed after every
    real commit so a human watching a live run can see actions/rules/
    accumulating unactivated files, without needing a full log
    post-mortem."""
    rules_root = ROOT / "actions" / "rules"
    rule_files = sorted(
        f"{action_dir.name}/{p.stem}"
        for action_dir in (rules_root.iterdir() if rules_root.is_dir() else [])
        if action_dir.is_dir() and action_dir.name != "__pycache__"
        for p in action_dir.glob("*.py") if p.stem != "__init__"
    )
    try:
        config = json.loads((ROOT / "state" / "config.json").read_text())
    except (OSError, json.JSONDecodeError):
        return "  [rule activation summary unavailable: state/config.json unreadable]"
    active_types = sorted(
        f"{action_name}:{spec.get('type')}"
        for action_name, specs in config.get("rules", {}).items()
        for spec in specs
    )
    # A rule file's stem isn't necessarily its type_name — this comparison
    # is approximate/observational, not the authoritative check (that's
    # norm_implementation_orphaned_norm_errors()).
    return (
        f"  Rule plugin inventory: {len(rule_files)} file(s) under actions/rules/, "
        f"{len(active_types)} type(s) currently active in state/config.json "
        f"({', '.join(active_types) if active_types else 'none'})."
    )


def record_institution_changes(round_number):
    """Diffs state/institution.json as of HEAD against the working tree
    (after a COMPLIANT round's own edits) via
    engine.institution.history.diff_institution(), and — only if that
    finds something structural — bumps institution.json's own "version"/
    "updated_at_round" fields and appends one line to
    state/institution_history.jsonl recording exactly what changed. This
    is the queryable "what changed and when" record
    engine.institution.history itself only computes; a purely parametric
    round (one that never touched institution.json's own catalogs) leaves
    both untouched. Called only from the COMPLIANT branch below — a
    discarded round's institution.json never reaches HEAD, so there's
    nothing to record for it."""
    institution_path = ROOT / "state" / "institution.json"
    head_result = subprocess.run(
        ["git", "show", "HEAD:state/institution.json"], cwd=ROOT, capture_output=True, text=True,
    )
    try:
        old = json.loads(head_result.stdout) if head_result.returncode == 0 else {}
    except json.JSONDecodeError:
        old = {}
    new = json.loads(institution_path.read_text())

    changes = diff_institution(old, new)
    if not changes:
        return

    new_version = old.get("version", 0) + 1
    new["version"] = new_version
    new["updated_at_round"] = round_number
    institution_path.write_text(json.dumps(new, indent=2) + "\n")

    history_path = ROOT / "state" / "institution_history.jsonl"
    with history_path.open("a") as f:
        f.write(json.dumps({"version": new_version, "round": round_number, "changes": changes}) + "\n")

    print(f"  Institution version bumped to {new_version} ({len(changes)} structural change(s) this round).")


def stage_norm_implementation(round_number):
    """Stages (git add only, never commits) the norm-implementer's tracked
    paths; the actual `git commit` happens in commit_round() below, which
    combines this with the round's own artifacts into a single commit.
    Staging happens here regardless of model behavior — the
    norm-implementer is unreliable about committing its own work."""
    subprocess.run(["git", "add"] + NORM_IMPLEMENTER_TRACKED_PATHS, cwd=ROOT, check=True)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()

    if not staged:
        print(f"Round {round_number}: norm-implementer made no changes in the tracked paths — nothing to commit.")
        log_call(
            call="norm_implementer_no_changes",
            agent_id=None, round=round_number, action=None, model=None,
            duration_s=None, returncode=None, prompt=None,
            raw_response=None, parsed_response=None, error=None,
        )
        return False

    print(_norm_activation_summary())
    return True


# Bounds real repair attempts (an IMPLEMENTATION_ERROR/SPEC_GAP finding, or
# a compile error) — a judgment about the code. Raised 2 -> 4 -> 10
# (2026-09-14) after a real round exhausted its budget on a genuine, well-
# evidenced code bug (a rule referencing an institutional object instance
# that was never declared) that survived one repair attempt because the
# model's own fix addressed a different, superficially-similar problem
# (an institution.json catalog path) instead of the actual missing
# instance. Distinct from the process-attempt budget defined below, which
# is about retrying an identical thing after a session-level glitch, not
# about giving a real fix more chances. Real cost, named explicitly: each
# unit here is a full implement-again + re-evaluate cycle (an opencode
# subprocess each), not a cheap retry — 10 is a genuinely large worst-case
# budget for one persistently-broken round, accepted deliberately for now
# to see how many real attempts a model actually needs against a clearly-
# quoted error before this number should be revisited downward instead.
MAX_NORM_REPAIR_ATTEMPTS = 10
# Separate bound for retrying the evaluator PROCESS itself when it fails to
# produce any verdict at all (timeout, crash, unparseable report) — that
# says nothing about whether the code is correct, so it must not consume a
# repair attempt or discard an otherwise-good round on its own. Raised
# 2 -> 5 (2026-09-14), matching MAX_IMPLEMENTER_PROCESS_ATTEMPTS: this is
# the same class of failure (a process-level retry, not a content-quality
# budget), and the 2-GPU/OLLAMA_SCHED_SPREAD/128k-context change made the
# same day is specifically aimed at the GPU-contention pressure behind a
# real share of these process failures — more attempts costs more only if
# that fix didn't help.
MAX_EVALUATOR_ATTEMPTS = 5
# Same idea, for the norm-implementer's own process. run_norm_implementer()
# returning False now covers three cases: a crash, a timeout, or a session
# that ended abnormally mid-task despite exiting 0 (see
# extract_last_step_reason()). Analyzing a real 12-round run found the
# third case alone accounted for roughly half of all invocations — treating
# any of these as an unretried hard failure (as a bare run_norm_implementer()
# call would) discarded close to half of all rounds before real work ever
# had a chance to happen, regardless of whether the eventual code would
# have been fine. Raised from 2 to 5 (2026-09-14) after a real round hit
# the identical "session ended abnormally (last step reason: 'tool-calls')"
# signature on both of its 2 allowed attempts and was discarded despite the
# actual code issue never having had a chance to be attempted — the failure
# looks session-level/transient, not a deterministic code problem, so a
# wider budget is worth the added worst-case wall time.
MAX_IMPLEMENTER_PROCESS_ATTEMPTS = 5
# A small pause between process-retry attempts — matches the existing
# CALL_DELAY_S convention in engine/llm_agents.py for fisher/critique call
# retries, but kept as its own env var since an opencode subprocess call is
# far heavier than one litellm completion; reusing LLM_CALL_DELAY_S would
# couple two unrelated costs.
NORM_IMPLEMENTER_RETRY_DELAY_S = float(os.environ.get("NORM_IMPLEMENTER_RETRY_DELAY_S", "5"))


def run_norm_implementer_with_retry(round_number, extra_message=None, session_id=None):
    """Retries run_norm_implementer() itself, up to
    MAX_IMPLEMENTER_PROCESS_ATTEMPTS times, on a process-level failure —
    this is not a finding about the code, so it must not be confused with
    or consume a MAX_NORM_REPAIR_ATTEMPTS repair attempt. Refreshes the
    knowledge graph before every real attempt (including retries), same as
    every other call site in this file. Returns (success, session_id) —
    same success contract as run_norm_implementer() itself.

    Each retry here continues the SAME opencode session (added
    2026-09-15, by request) rather than starting fresh: session_id starts
    as whatever the caller passed in (None for a genuinely fresh start)
    and is updated after every attempt — including a failed one — to
    whatever run_norm_implementer() actually used, so attempt 2 continues
    attempt 1's session instead of re-deriving everything about the round
    from scratch by re-reading files a previous session already read."""
    current_session_id = session_id
    for attempt in range(1, MAX_IMPLEMENTER_PROCESS_ATTEMPTS + 1):
        refresh_knowledge_graph(round_number)
        success, current_session_id = run_norm_implementer(
            round_number, extra_message=extra_message, session_id=current_session_id
        )
        if success:
            return True, current_session_id
        print(f"Round {round_number}: norm-implementer's own process failed, timed out, or was "
              f"truncated mid-task (attempt {attempt}/{MAX_IMPLEMENTER_PROCESS_ATTEMPTS}) — "
              f"retrying the process itself, not spending a repair attempt on it.")
        if attempt < MAX_IMPLEMENTER_PROCESS_ATTEMPTS:
            time.sleep(NORM_IMPLEMENTER_RETRY_DELAY_S)
    return False, current_session_id


def implement_and_evaluate_norm(round_number, winning_proposal):
    """The per-round pipeline: implement -> compile/runtime-check (with its
    own bounded repair retry) -> independent evaluation -> repair-or-stage.
    A loop because both a compile error and an evaluator NEEDS_REPAIR
    finding can send the norm-implementer back for another attempt,
    sharing one MAX_NORM_REPAIR_ATTEMPTS budget. Returns True iff the
    norm-implementer's changes were staged (ready for commit_round()'s own
    single per-round commit); False means either a discard already
    happened, or the round was COMPLIANT but made no changes to stage.

    Refreshes the knowledge graph immediately before every
    run_norm_implementer()/run_norm_evaluator() call in this function
    (not just after a commit) so it's fresh at the moment each agent
    actually reads it — a no-op unless BUILD_KNOWLEDGE_GRAPH=1.

    Two opencode sessions are tracked across this whole function — one for
    the norm-implementer, one for the norm-evaluator (added 2026-09-15, by
    request) — and continued (--session <id>) across every retry for that
    agent within this round: a process retry, a compile-error repair, and
    an evaluator NEEDS_REPAIR repair all reuse the implementer's one
    session; the evaluator's own process retries reuse its one session.
    Neither carries over to a different round — implement_and_evaluate_norm()
    is called fresh per round, so a genuinely new round always starts both
    agents with session_id=None (no continuation), same as before this
    change."""
    implementer_session_id = None
    evaluator_session_id = None

    success, implementer_session_id = run_norm_implementer_with_retry(round_number)
    if not success:
        discard_norm_implementation(
            round_number,
            [f"norm-implementer's process failed, timed out, or was truncated on every attempt "
             f"(after {MAX_IMPLEMENTER_PROCESS_ATTEMPTS} tries) — see ops/logs/model_calls.jsonl"],
        )
        return False

    for attempt in range(1, MAX_NORM_REPAIR_ATTEMPTS + 2):
        # Protected-path violations are a hard, non-retryable discard —
        # a boundary violation, not a bug to repair.
        protected_violations = norm_implementation_protected_path_violations()
        if protected_violations:
            discard_norm_implementation(round_number, protected_violations)
            return False

        compile_errors = norm_implementation_compile_errors()
        compile_errors += norm_implementation_institution_errors()
        compile_errors += norm_implementation_orphaned_norm_errors()
        compile_errors += norm_implementation_missing_spec_errors(round_number)
        if not compile_errors:
            compile_errors += norm_implementation_unverified_requirements_errors(round_number)
        if not compile_errors:
            compile_errors += norm_implementation_no_code_changes_errors()
        if not compile_errors:
            runtime_error = norm_implementation_runtime_errors()
            if runtime_error:
                compile_errors = [runtime_error]
        if compile_errors:
            if attempt > MAX_NORM_REPAIR_ATTEMPTS:
                discard_norm_implementation(round_number, compile_errors)
                return False
            print(f"\nRound {round_number}: norm-implementer's changes have compile/validation "
                  f"errors — sending back for repair (attempt {attempt}/{MAX_NORM_REPAIR_ATTEMPTS}), "
                  f"instead of discarding on the first occurrence.")
            repair_message = (
                f"Round {round_number}'s implementation has compile/validation errors that must "
                f"be fixed before it can even be evaluated:\n\n{chr(10).join(compile_errors)}\n\n"
                "Fix exactly these errors, then re-run your own verification step "
                "(python3 -m py_compile on every file you touched, plus pytest tests/regression/ "
                "and tests/norm_checks/) yourself before finishing — don't rely on this message "
                "alone to catch the next issue. Don't change anything else about your "
                "implementation beyond what's needed to fix these specific errors. End your "
                "response with the fenced ```json report block your instructions describe."
            )
            success, implementer_session_id = run_norm_implementer_with_retry(
                round_number, extra_message=repair_message, session_id=implementer_session_id
            )
            if not success:
                discard_norm_implementation(
                    round_number,
                    [f"norm-implementer's repair run failed, timed out, or was truncated on every "
                     f"attempt (after {MAX_IMPLEMENTER_PROCESS_ATTEMPTS} tries) — see "
                     f"ops/logs/model_calls.jsonl"],
                )
                return False
            continue

        evaluation = None
        evaluator_message = None
        for eval_attempt in range(1, MAX_EVALUATOR_ATTEMPTS + 1):
            refresh_knowledge_graph(round_number)
            evaluation, evaluator_session_id = run_norm_evaluator(
                round_number, extra_message=evaluator_message, session_id=evaluator_session_id
            )
            if evaluation is not None:
                break
            print(f"Round {round_number}: norm-evaluator itself produced no usable verdict "
                  f"(attempt {eval_attempt}/{MAX_EVALUATOR_ATTEMPTS}) — retrying the evaluator, "
                  f"not the implementation, since this doesn't say anything about whether the "
                  f"code is actually correct.")
            # This retry continues the SAME session (session_id above) as
            # of 2026-09-15 — the model genuinely does have real memory of
            # the earlier attempt now, so unlike before this change the
            # message doesn't deny that; it just states plainly what went
            # wrong and what's needed this time.
            evaluator_message = (
                f"Your last response for round {round_number} ended without the required "
                "EVALUATION_RESULT: line — treating that as an incomplete evaluation, not a "
                "verdict. If you already read norm.txt, the spec, and the diff, and already "
                "wrote/ran tests, don't redo that work — just finish: reach a verdict from what "
                "you already found and end your response with EVALUATION_RESULT: COMPLIANT or "
                "EVALUATION_RESULT: NEEDS_REPAIR, in exactly that form. If you got interrupted "
                "before actually reading the spec/diff or running any tests, do that now, then "
                "end with the same required line."
            )
        if evaluation is None:
            discard_norm_implementation(
                round_number,
                [f"norm-evaluator failed to produce a parseable verdict after "
                 f"{MAX_EVALUATOR_ATTEMPTS} attempts — see ops/logs/model_calls.jsonl"],
            )
            return False

        if evaluation["result"] == "COMPLIANT":
            record_institution_changes(round_number)
            return stage_norm_implementation(round_number)

        # The evaluator's own free-text report is handed back verbatim as
        # the repair prompt — no structured verdict list to re-parse.
        if attempt > MAX_NORM_REPAIR_ATTEMPTS:
            discard_norm_implementation(
                round_number,
                [f"norm-evaluator returned NEEDS_REPAIR after {MAX_NORM_REPAIR_ATTEMPTS} repair "
                 f"attempt(s). Evaluator's final report:\n\n{evaluation['text']}"],
            )
            return False

        print(f"\nRound {round_number}: norm-evaluator returned NEEDS_REPAIR — sending back to "
              f"norm-implementer (repair attempt {attempt}/{MAX_NORM_REPAIR_ATTEMPTS}).")
        repair_message = (
            f"Round {round_number}'s evaluator found problems — read its full report below "
            "carefully and fix exactly what it identifies. If it's a code/implementation "
            "problem, fix the implementation. If it's a genuine gap in the specification (an "
            f"ambiguity the evaluator's own tests exposed), redo that requirement's "
            f"clarification in state/norm_specs/round_{round_number}.md (ask a sharper question "
            "than last time), then adjust the implementation for whatever the resolution "
            "changes. Follow your standing instructions for handling a repair re-invocation. "
            "End your response with the fenced ```json report block your instructions "
            "describe.\n\n"
            f"--- Evaluator's report ---\n{evaluation['text']}\n--- end of report ---"
        )
        success, implementer_session_id = run_norm_implementer_with_retry(
            round_number, extra_message=repair_message, session_id=implementer_session_id
        )
        if not success:
            discard_norm_implementation(
                round_number,
                [f"norm-implementer's repair run failed, timed out, or was truncated on every "
                 f"attempt (after {MAX_IMPLEMENTER_PROCESS_ATTEMPTS} tries) — see "
                 f"ops/logs/model_calls.jsonl"],
            )
            return False

    return False  # unreachable — the loop above always returns first


ROUND_ARTIFACT_PATHS = [
    "ops/logs",
    "norm.txt",
    "ops/plots",
    "state/runtime.json",
    # A compiled artifact now (engine.institution.scheduler.compile_schedule(),
    # regenerated every round by compile_and_write_schedule()), never
    # hand-edited — committed like any other simulation-derived output,
    # never reverted on a discard (it's recomputed fresh next round from
    # whatever institution.json/state/actions survive the discard anyway).
    "state/schedule.json",
    # Written by record_institution_changes(), only ever after a COMPLIANT
    # round — orchestrator-owned, never a norm-implementer edit target
    # (institution.json's own content is; the version/history bookkeeping
    # derived from it isn't).
    "state/institution_history.jsonl",
    # constants/agents.json is deliberately NOT here — it's fixed for the
    # life of a run, only generate_agents.py rewrites it, so it doesn't
    # need re-staging every round.
    # The institutional design spec — always preserved (forensic record of
    # what was analyzed) even when the round's actual code is discarded.
    "state/norm_specs",
]


def commit_round(round_number, winning_proposal):
    """The single commit for this round — combines whatever
    stage_norm_implementation() already staged with this round's own
    artifacts (logs, norm.txt, runtime state, plots), unconditionally,
    regardless of whether this round's norm committed, was a no-op, or
    got discarded. `winning_proposal` is only passed when a norm was
    actually staged this round; otherwise the commit uses a generic
    artifacts message.

    Kept as a separate `git add` from NORM_IMPLEMENTER_TRACKED_PATHS'S own
    staging (not merged into one list): that list also scopes what
    discard_norm_implementation() may `git clean -fd`, and ops/logs and
    norm.txt are exactly the forensic record of *why* a round was
    discarded — they must never be at risk of being wiped by the discard
    they explain."""
    existing = [p for p in ROUND_ARTIFACT_PATHS if (ROOT / p).exists()]
    if existing:
        subprocess.run(["git", "add"] + existing, cwd=ROOT, check=True)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    if not staged:
        return

    if winning_proposal:
        message = f"Round {round_number} norm: {winning_proposal['policy']}\n\n{winning_proposal['operationalization']}"
    else:
        message = f"Round {round_number} artifacts: logs, norm.txt, runtime state, plots"
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True, capture_output=True, text=True)
    commit_hash = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()

    if winning_proposal:
        print(f"Committed round {round_number} as {commit_hash}: {winning_proposal['policy'][:72]}")
        # Distinct from norm_implementer_discarded/norm_implementer_no_changes
        # so a plot can read a clean, mutually-exclusive per-round signal.
        log_call(
            call="norm_implementer_committed",
            agent_id=None, round=round_number, action=None, model=None,
            duration_s=None, returncode=None, prompt=None,
            raw_response=None, parsed_response=None, commit_hash=commit_hash, error=None,
        )
    else:
        print(f"Round {round_number}: committed round artifacts as {commit_hash} "
              f"(logs, norm.txt, runtime state, plots).")


def refresh_knowledge_graph(round_number):
    """Refreshes the Understand-Anything semantic graph after code changes,
    so it doesn't stay frozen at whatever it looked like before round 1.
    Run directly here as its own `build`-agent opencode call, rather than
    via the plugin's own autoUpdate hooks — those assume the committing
    agent is the one running `git commit` (this project commits via a
    plain subprocess) and would otherwise burn norm-implementer step
    budget on an instruction it's structurally unable to follow
    (permission.task: deny blocks the subagent dispatch a graph update
    needs). Gated by BUILD_KNOWLEDGE_GRAPH=1, matching whatever
    hpc_ollama_entrypoint.sh did at job start; no-op if unset. Failure here
    is never fatal to the round."""
    if os.environ.get("BUILD_KNOWLEDGE_GRAPH") != "1":
        return
    print(f"\n--- refreshing Understand-Anything knowledge graph (round {round_number}) ---")
    # --command names the skill directly (a prose message doesn't reliably
    # get inferred as one). --format json so raw_response actually captures
    # the session (opencode's default format writes to stderr, not stdout).
    # --auto because the build agent's external_directory permission
    # defaults to "ask", and nothing is present to answer it headlessly.
    cmd = ["opencode", "run", "--agent", "build", "--format", "json", "--auto"]
    # Uses OPENCODE_MODEL (local), not a paid litellm model — UA's calls
    # are large enough to risk exceeding a paid quota for this opt-in
    # feature; the two known local-model reliability gaps (a hallucinated
    # tool name, ignoring the unattended-mode instruction) are an accepted
    # limitation rather than routed around.
    model = os.environ.get("OPENCODE_MODEL")
    if model:
        cmd += ["--model", model]
    # Trailing message required — --command alone loads the skill into
    # context and stops without executing a single phase.
    cmd += ["--command", "understand", "--", "--no-auto-update",
            "Begin the analysis immediately, following the skill's own instructions completely — "
            "do not wait for further input."]

    start = time.monotonic()
    try:
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        print(f"Round {round_number}: knowledge graph refresh timed out after 600s — continuing "
              f"with the graph as it was; norm-implementer's own staleness check will flag this.")
        log_call(
            call="knowledge_graph_refresh", agent_id=None, round=round_number, action=None,
            model=model, duration_s=600.0, returncode=None, prompt=" ".join(cmd),
            raw_response=None, parsed_response=None, error="timeout",
        )
        return

    duration_s = time.monotonic() - start
    tool_call_count, step_count, final_text = parse_opencode_jsonl(result.stdout)
    # Exit code alone isn't trustworthy — a silent no-op has been observed
    # to still return 0. Verify the graph's own stored commit hash actually
    # caught up to HEAD.
    error = None if result.returncode == 0 else result.stderr.strip()
    if error is None and not knowledge_graph_matches_head():
        error = "opencode exited 0 but the graph's stored commit hash didn't advance to HEAD — likely a silent no-op"
    if error:
        print(f"Round {round_number}: knowledge graph refresh FAILED ({error}) — continuing "
              f"with the graph as it was; norm-implementer's own staleness check will flag "
              f"this. Model's final response:\n{final_text}", file=sys.stderr)
    else:
        print(f"Round {round_number}: knowledge graph refresh OK ({tool_call_count} tool calls, "
              f"{duration_s:.1f}s) — graph now matches HEAD.")
    log_call(
        call="knowledge_graph_refresh", agent_id=None, round=round_number, action=None,
        model=model, duration_s=round(duration_s, 3), returncode=result.returncode,
        prompt=" ".join(cmd), raw_response=result.stdout, tool_call_count=tool_call_count,
        step_count=step_count,
        parsed_response=final_text, error=error,
    )


def knowledge_graph_matches_head():
    """True iff a knowledge graph exists and its stored gitCommitHash
    (meta.json) equals current HEAD — the only reliable way to tell a
    refresh actually did something, since a failed/no-op call can still
    exit 0."""
    for data_dir in (".understand-anything", ".ua"):
        meta_path = ROOT / data_dir / "meta.json"
        if meta_path.is_file():
            try:
                stored_hash = json.loads(meta_path.read_text()).get("gitCommitHash")
            except (json.JSONDecodeError, OSError):
                return False
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
            ).stdout.strip()
            return stored_hash == head
    return False


def reload_project_modules():
    """Python caches imported modules for the life of the process — without
    this, a norm-implementer edit to roles/*.py, actions/handlers/*.py,
    actions/rules/{action}/*.py, or objects/handlers/*.py never takes
    effect within a single continuous run.

    Unlike the old norms/-based design, no eager, computed-once registry
    needs a separate rebind step any more: rule/action-handler/
    object-handler discovery (engine.institution.rules.discover_rule_types(),
    engine.institution.runtime.resolve_handler(),
    ObjectRuntime.custom()'s discover_handlers() call) is always a fresh
    importlib.import_module() call, never cached at module-import time —
    so reloading the module that DEFINES a plugin is sufficient on its
    own; there's no second module holding a stale snapshot of what it
    found. This is a genuine simplification over the old design, not just
    a rename: the whole "reload order matters, rebind NORM_TYPES, then
    rebind engine.norms.engine's own import of it" dance that NORM_TYPES's
    eager caching used to require doesn't have an equivalent problem to
    solve any more.

    engine/institution/*.py itself is deliberately never reloaded here —
    it's off-limits to the norm-implementer by construction (nothing in
    it is on any tracked-path list), so nothing there can change mid-run."""
    for prefix in ("roles", "actions", "objects"):
        for name in sorted(n for n in list(sys.modules) if n == prefix or n.startswith(prefix + ".")):
            importlib.reload(sys.modules[name])


def run_cycle(round_number):
    """Runs every state/schedule.json action gated on for this round, in
    file order. Skips actions already recorded for this round (resuming
    after a crash mid-round). Returns False if the lake collapsed."""
    print(f"\n=== Round {round_number} ===")
    reload_project_modules()
    state = load_state(round_number)
    schedule = compile_and_write_schedule()
    already_ran = {r["action"] for r in state["runtime"]["rounds"] if r["round"] == round_number}

    tick_rule_lifecycles(state["config"], state["fluents"], round_number)
    round_rules = all_configured_rules(state["config"], round_number)
    for rule in round_rules:
        rule.before_round(state, round_number)

    for action_name, gate in schedule.items():
        if action_name in already_ran:
            print(f"--- {action_name}: already recorded for round {round_number}, resuming past it ---")
            continue
        if not evaluate_gate(gate, state["fluents"], round_number):
            print(f"--- {action_name}: gated off this round ---")
            continue

        print(f"\n--- Round {round_number}: {action_name} ---")
        action_spec = load_action_spec(action_name)
        record = ActionRuntime.run_action(action_spec, state, round_number)
        save_runtime(state)
        save_fluents(state)
        save_events(state)
        print(json.dumps(record, indent=2))
        write_memory_episodes(action_spec, state, record, round_number)

        if state["runtime"]["stock_kg"] <= COLLAPSE_THRESHOLD_KG:
            print(
                f"\nLake has collapsed at round {round_number} "
                f"(stock_kg={state['runtime']['stock_kg']}). Stopping."
            )
            # Commit here too — this early return otherwise skips
            # update_plots()/commit_round() below, and the round that ends
            # the run is exactly the one that must not lose its data.
            commit_round(round_number, None)
            return False

    for rule in round_rules:
        rule.after_round(state, round_number)

    write_fact_memory_events(state, round_number)
    write_event_memory_episodes(state, round_number)

    winning_proposal = state.get("adopted_norm") or find_adopted_norm(state["runtime"], round_number)
    norm_staged = False
    if winning_proposal:
        if norm_already_committed(round_number):
            print(f"\nRound {round_number}: norm-implementer already committed for this round, skipping.")
        else:
            norm_text = (
                f"Policy: {winning_proposal['policy']}\n\n"
                f"Operationalization: {winning_proposal['operationalization']}\n"
            )
            (ROOT / "norm.txt").write_text(norm_text)
            print(f"\nAdopted norm written to norm.txt:\n{norm_text}")
            norm_staged = implement_and_evaluate_norm(round_number, winning_proposal)

    update_plots(state)
    # winning_proposal only becomes the commit message when something was
    # actually staged this round — otherwise this is purely an artifacts
    # commit.
    commit_round(round_number, winning_proposal if norm_staged else None)

    return True


def round_is_complete(runtime, fluents, schedule, round_number):
    recorded = {r["action"] for r in runtime["rounds"] if r["round"] == round_number}
    expected = {name for name, gate in schedule.items() if evaluate_gate(gate, fluents, round_number)}
    return expected.issubset(recorded)


def ensure_run_branch():
    """Never let a run's state/code changes or norm-implementer commits land
    on whatever branch we happened to start on (main included). If we're
    already on a sim/ run branch, keep going on it; otherwise cut a new one."""
    current = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()

    if current.startswith("sim/"):
        print(f"Continuing on existing run branch: {current}")
        return current

    branch = f"sim/run-{time.strftime('%Y%m%d-%H%M%S')}"
    subprocess.run(["git", "checkout", "-b", branch], cwd=ROOT, check=True, capture_output=True, text=True)
    print(f"Started new run on branch: {branch} (branched from {current})")

    dirty = subprocess.run(
        ["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    if dirty:
        print("Carried these uncommitted changes onto the new branch:")
        print(dirty)

    return branch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=DEFAULT_MAX_ROUNDS,
        help="Safety backstop: stop after this many total rounds even if the lake hasn't collapsed.",
    )
    args = parser.parse_args()

    branch = ensure_run_branch()

    runtime = json.loads((ROOT / "state" / "runtime.json").read_text())
    fluents = json.loads((ROOT / "state" / "fluents.json").read_text())
    schedule = compile_and_write_schedule()

    last_round = runtime["round"]
    if last_round > 0 and not round_is_complete(runtime, fluents, schedule, last_round):
        round_number = last_round
        print(f"Round {round_number} didn't finish last time — resuming it.")
    else:
        round_number = last_round + 1

    while round_number <= args.max_rounds:
        if not run_cycle(round_number):
            print(f"\n=== Simulation ended: lake collapse at round {round_number} ===")
            break
        round_number += 1
    else:
        print(f"\n=== Simulation ended: reached the {args.max_rounds}-round safety cap without collapse ===")

    print(
        f"\nAll of this run's commits are on branch '{branch}', not main.\n"
        f"  git log main..{branch} --oneline   # see what this run did\n"
        f"  git checkout main                  # main is untouched\n"
        f"  git merge --ff-only {branch}        # bring it into main once you're happy with it"
    )


if __name__ == "__main__":
    main()
