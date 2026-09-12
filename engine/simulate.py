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

try:
    # matplotlib may be missing from a minimal venv; monitoring is optional.
    from engine.monitoring import update_plots
except ImportError as exc:
    print(f"  [monitoring disabled: {exc}]")

    def update_plots(state):
        pass

ROOT = Path(__file__).resolve().parent.parent
# Dedicated per-agent logs, written alongside the shared logs/model_calls.jsonl.
NORM_IMPLEMENTER_LOG_PATH = ROOT / "logs" / "norm_implementer.jsonl"
NORM_EVALUATOR_LOG_PATH = ROOT / "logs" / "norm_evaluator.jsonl"
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
    "norms",
    "actions",
    "objects",
    "prompts",
    # Implementer-authored tests for its own norm/action changes.
    "tests/norm_checks",
    # The norm-evaluator's own generated tests — must revert alongside the
    # norms/*.py code they test if this round is discarded.
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
    "engine/norms",
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
        # path" principle norms/*.py already uses. Object INSTANCE
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
    norms/*.py and state/object_types/*.json."""
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
    stream parse_opencode_jsonl() reads — feeds logs/norm_implementer.jsonl
    / logs/norm_evaluator.jsonl. A tool named "invalid" means the model
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


def run_norm_implementer(round_number, extra_message=None):
    """Runs the norm-implementer as an opencode subprocess. Returns True on
    a clean (returncode 0) run that also ended on a genuine "stop" (see
    extract_last_step_reason()), False on any failure — a timeout, a
    crash, a non-zero exit, or a session that was silently truncated
    mid-task despite exiting 0. Analyzing a real 12-round run found this
    last case is common (13 of 26 real invocations never reached a
    deliberate stop) and is very likely why code-writing specifically
    (which tends to happen only after exploration/spec-writing) so rarely
    got reached at all — not because the implementation itself was too
    costly to attempt. The caller treats False like a compile error:
    discard this round's changes and continue, rather than crashing the
    whole multi-round run or trusting partial work as if it were final."""
    print("\n--- invoking norm-implementer ---")
    # State the round number explicitly — the model can't reliably infer it
    # from file contents alone. Also restates the closing-json-block
    # requirement on every invocation, not just on repair.
    message = extra_message or (
        f"This is round {round_number}. norm.txt has been updated for this round. "
        f"Read it and implement accordingly, following your standing instructions. "
        f"Write your institutional design specification to exactly "
        f"state/norm_specs/round_{round_number}.md "
        f"— use {round_number} for the round number, not a number inferred from any other file. "
        f"End your response with the fenced ```json report block your instructions describe "
        f"(the one containing a \"classification\" key) — this is required every time, not "
        f"just when something went wrong."
    )
    cmd = ["opencode", "run", "--agent", "norm-implementer", "--format", "json"]
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
    except subprocess.TimeoutExpired:
        duration_s = time.monotonic() - start
        print(f"Round {round_number}: norm-implementer didn't finish within 3600s — "
              f"treating this round's norm implementation as failed, not crashing the run.",
              file=sys.stderr)
        log_call(
            also_log_to=NORM_IMPLEMENTER_LOG_PATH,
            call="norm_implementer", agent_id=None, round=round_number, action=None,
            model=model, duration_s=round(duration_s, 3), returncode=None,
            prompt=message, raw_response=None, parsed_response=None,
            tool_call_count=None, step_count=None, tool_call_trace=None,
            last_step_reason=None,
            report=None, error="timeout after 3600s",
        )
        return False

    duration_s = time.monotonic() - start
    tool_call_count, step_count, final_text = parse_opencode_jsonl(result.stdout)
    tool_call_trace = extract_tool_trace(result.stdout)
    last_step_reason = extract_last_step_reason(result.stdout)
    report = extract_json_report(final_text, required_keys={"classification"})

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
        return False
    if truncated:
        print(f"Round {round_number}: norm-implementer's session ended abnormally (last step "
              f"reason: {last_step_reason!r}, not a genuine 'stop') — likely a failed or "
              f"truncated completion call, not a deliberate finish. Treating this round's "
              f"partial work as failed rather than trusting it.", file=sys.stderr)
        return False
    return True


def run_norm_evaluator(round_number, extra_message=None):
    """Mirrors run_norm_implementer()'s subprocess/timeout/logging shape,
    against the norm-evaluator agent. Returns
    {"result": "COMPLIANT" | "NEEDS_REPAIR", "text": final_text} on a
    completed run whose response contains a trusted sentinel line (see
    extract_evaluation_result() and the zero-tool-call check below), or
    None on any failure — treated by the caller like a norm-implementer
    failure: discard, don't crash the rest of the run."""
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
    cmd = ["opencode", "run", "--agent", "norm-evaluator", "--format", "json"]
    # Same fallback as run_norm_implementer() — no reason yet to route this
    # agent to a different model than the implementer it's paired with.
    model = os.environ.get("NORM_IMPLEMENTER_MODEL") or os.environ.get("OPENCODE_MODEL")
    if model:
        cmd += ["--model", model]
    cmd.append(message)

    start = time.monotonic()
    try:
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        duration_s = time.monotonic() - start
        print(f"Round {round_number}: norm-evaluator didn't finish within 1800s — "
              f"treating this evaluation as failed, not crashing the run.", file=sys.stderr)
        log_call(
            also_log_to=NORM_EVALUATOR_LOG_PATH,
            call="norm_evaluator", agent_id=None, round=round_number, action=None,
            model=model, duration_s=round(duration_s, 3), returncode=None,
            prompt=message, raw_response=None, parsed_response=None,
            tool_call_count=None, step_count=None, tool_call_trace=None,
            report=None, error="timeout after 1800s",
        )
        return None

    duration_s = time.monotonic() - start
    tool_call_count, step_count, final_text = parse_opencode_jsonl(result.stdout)
    tool_call_trace = extract_tool_trace(result.stdout)
    verdict = extract_evaluation_result(final_text)

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
        return None
    if verdict is None:
        print(f"Round {round_number}: norm-evaluator's response never contained an "
              f"EVALUATION_RESULT: line — treating this evaluation as failed.", file=sys.stderr)
        return None
    if zero_tool_call_reject:
        return None
    return {"result": verdict, "text": final_text}


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
    # file, and confirms every norm "type" referenced in state/config.json
    # resolves to a real registered class (checked in a fresh subprocess so
    # a stale in-process NORM_TYPES snapshot can't hide a type just added).
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
                "from engine.norms.registry import load_norms\n"
                "config = json.loads(open('state/config.json').read())\n"
                "load_norms(config)\n"
            )],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if check.returncode != 0:
            errors.append(f"state/config.json (norm type check):\n{check.stderr.strip()}")
    return errors


def norm_implementation_runtime_errors():
    # Actually runs the harvest action through the new declarative
    # ActionContext/ActionRuntime (no real LLM call, monkeypatched fisher
    # response) — once using whatever config.json currently activates,
    # then once per registered norm type standalone with generic params,
    # so a type that's never wired into config still gets exercised. Also
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
        "import actions.handlers.harvest as harvest_handler\n"
        "from engine.norms.registry import NORM_TYPES\n"
        "from engine.norms.context import HarvestContext\n"
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
        "context = HarvestContext.from_state({\n"
        "    'config': {}, 'fluents': [], 'runtime': {'stock_kg': 200.0},\n"
        "    'agents': {}, 'round_number': 1,\n"
        "})\n"
        "errors = []\n"
        "for type_name, cls in sorted(NORM_TYPES.items()):\n"
        "    try:\n"
        "        norm = cls(key=type_name, params={})\n"
        "        norm.on_round_start(context)\n"
        "        norm.is_eligible(context, 'agent_0')\n"
        "        norm.describe(context, 'agent_0')\n"
        "        decision = norm.evaluate(context, 'agent_0', raw_kg=20.0, proposed_kg=20.0)\n"
        "        norm.on_agent_settled(context, 'agent_0', decision, decision.kept_kg)\n"
        "        norm.on_round_end(context, {'agent_0': {\n"
        "            'harvested_kg': decision.kept_kg, 'effort': 0.5,\n"
        "            'participated': True, 'note': decision.note,\n"
        "        }})\n"
        "    except Exception as exc:\n"
        "        errors.append(f'{type_name}: {type(exc).__name__}: {exc}')\n"
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
            "Institution runtime check (active config + every registered norm type + "
            "every new state/actions/*.json spec's execution.handler + every "
            f"state/object_types/*.json type's custom_handler, if any):\n{detail}"
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
    a norm_types/object_types entry whose owner file doesn't exist — any
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

    # Same drift-check pattern for norm_types/object_types: only checks
    # path existence, not that the file's own type_name matches — that
    # stronger check is norm_implementation_orphaned_norm_errors() below
    # (norm_types only, for now — see CLAUDE.md-equivalent notes on
    # object-type orphan checking being deferred).
    for catalog_key in ("norm_types", "object_types"):
        for name, entry in institution.get(catalog_key, {}).items():
            owner = entry.get("owner")
            if owner and not (ROOT / owner).is_file():
                errors.append(
                    f"state/institution.json {catalog_key}[{name!r}] names owner "
                    f"{owner!r} but that file doesn't exist"
                )
    return errors


def norm_implementation_orphaned_norm_errors():
    """Catches a norm-implementer round that creates a new norms/{name}.py
    plugin (a real, correctly-written Norm subclass) without adding its
    type_name to state/config.json's "norms" list — the class compiles and
    passes every other check, but NormEngine.from_config() never loads it,
    so it silently never runs. Only checks norms/*.py files this round
    actually touched (an existing, deliberately unreferenced plugin from
    an earlier round is not an error).

    Uses `git status --porcelain`, not `git diff --name-only HEAD` — a
    brand-new file is untracked at this point in the pipeline, and `git
    diff` never shows untracked files."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "norms"],
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
    active_types = {spec.get("type") for spec in config.get("norms", [])}

    # Re-discover fresh in a subprocess — this runs before
    # reload_project_modules() would pick up what this round just wrote.
    script = (
        "import sys, json\n"
        "sys.path.insert(0, '.')\n"
        "from engine.norms.registry import NORM_TYPES\n"
        "touched = json.loads(sys.argv[1])\n"
        "out = {}\n"
        "for type_name, cls in NORM_TYPES.items():\n"
        "    module_path = cls.__module__.replace('.', '/') + '.py'\n"
        "    if module_path in touched:\n"
        "        out.setdefault(module_path, []).append(type_name)\n"
        "print(json.dumps(out))\n"
    )
    check = subprocess.run(
        [sys.executable, "-c", script, json.dumps(touched)],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    if check.returncode != 0:
        detail = check.stdout.strip() or check.stderr.strip()
        return [f"norm-type discovery for orphan check failed:\n{detail}"]
    try:
        types_by_file = json.loads(check.stdout.strip())
    except json.JSONDecodeError:
        return []  # discovery itself is exercised separately by the runtime check

    errors = []
    for module_path, type_names in sorted(types_by_file.items()):
        if not any(t in active_types for t in type_names):
            errors.append(
                f"{module_path} defines type_name(s) {type_names} but none of them "
                f'appear in state/config.json\'s "norms" list — this plugin will '
                f"never actually run in the simulation until one is added there. "
                f'Add {{"type": "{type_names[0]}", ...}} (with whatever params it '
                f"needs) to state/config.json's \"norms\" list, or remove the file "
                f"if it was never meant to be active yet."
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
            "design specification (institution designer stage) must be written and "
            "committed to exactly this path before any implementation or evaluation."
        ]
    if len(spec_path.read_text().strip()) < 200:
        return [
            f"state/norm_specs/round_{round_number}.md exists but is too short to be a "
            "real per-requirement specification — write the full spec, not a placeholder."
        ]
    return []


def norm_implementation_no_code_changes_errors():
    """Catches a real, repeatedly-observed failure distinct from a missing
    spec: the norm-implementer writes a real, substantive spec (passing
    norm_implementation_missing_spec_errors above) and then simply stops,
    genuinely believing the round is done — one real round's own closing
    report was literally {"classification": "success", "message": "Round 8
    norm specification written..."}, nothing else, not even the documented
    report schema. Checked here mechanically via git status against
    NORM_IMPLEMENTER_TRACKED_PATHS (state/norm_specs is deliberately not on
    that list, so a spec-only round leaves nothing there to see) — never by
    trusting the model's own self-reported classification, which doesn't
    reliably match the real schema anyway.

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
        "You wrote a real institutional design specification but made zero actual "
        "code/config/fluent changes — norms/*.py, actions/*.py, state/config.json, "
        "state/fluents.json, and state/institution.json are all untouched. Writing the "
        "specification is not the end of your task, it's the halfway point: you must now "
        "implement every requirement in your own classification table, in this same "
        "response, before finishing. A closing report claiming success with no files "
        "touched is not a legitimate success."
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
    real commit so a human watching a live run can see norms/ accumulating
    unactivated files, without needing a full log post-mortem."""
    norm_files = sorted(
        p.stem for p in (ROOT / "norms").glob("*.py") if p.stem != "__init__"
    )
    try:
        config = json.loads((ROOT / "state" / "config.json").read_text())
    except (OSError, json.JSONDecodeError):
        return "  [norm activation summary unavailable: state/config.json unreadable]"
    active_types = sorted({spec.get("type") for spec in config.get("norms", [])})
    # A norm file's stem isn't necessarily its type_name — this comparison
    # is approximate/observational, not the authoritative check (that's
    # norm_implementation_orphaned_norm_errors()).
    return (
        f"  Norm plugin inventory: {len(norm_files)} file(s) in norms/, "
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
# a compile error) — a judgment about the code.
MAX_NORM_REPAIR_ATTEMPTS = 2
# Separate bound for retrying the evaluator PROCESS itself when it fails to
# produce any verdict at all (timeout, crash, unparseable report) — that
# says nothing about whether the code is correct, so it must not consume a
# repair attempt or discard an otherwise-good round on its own.
MAX_EVALUATOR_ATTEMPTS = 2
# Same idea, for the norm-implementer's own process. run_norm_implementer()
# returning False now covers three cases: a crash, a timeout, or a session
# that ended abnormally mid-task despite exiting 0 (see
# extract_last_step_reason()). Analyzing a real 12-round run found the
# third case alone accounted for roughly half of all invocations — treating
# any of these as an unretried hard failure (as a bare run_norm_implementer()
# call would) discarded close to half of all rounds before real work ever
# had a chance to happen, regardless of whether the eventual code would
# have been fine.
MAX_IMPLEMENTER_PROCESS_ATTEMPTS = 2


def run_norm_implementer_with_retry(round_number, extra_message=None):
    """Retries run_norm_implementer() itself, up to
    MAX_IMPLEMENTER_PROCESS_ATTEMPTS times, on a process-level failure —
    this is not a finding about the code, so it must not be confused with
    or consume a MAX_NORM_REPAIR_ATTEMPTS repair attempt. Refreshes the
    knowledge graph before every real attempt (including retries), same as
    every other call site in this file — a no-op unless
    BUILD_KNOWLEDGE_GRAPH=1. Same True/False contract as
    run_norm_implementer() itself."""
    for attempt in range(1, MAX_IMPLEMENTER_PROCESS_ATTEMPTS + 1):
        refresh_knowledge_graph(round_number)
        if run_norm_implementer(round_number, extra_message=extra_message):
            return True
        print(f"Round {round_number}: norm-implementer's own process failed, timed out, or was "
              f"truncated mid-task (attempt {attempt}/{MAX_IMPLEMENTER_PROCESS_ATTEMPTS}) — "
              f"retrying the process itself, not spending a repair attempt on it.")
    return False


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
    actually reads it — a no-op unless BUILD_KNOWLEDGE_GRAPH=1."""
    if not run_norm_implementer_with_retry(round_number):
        discard_norm_implementation(
            round_number,
            [f"norm-implementer's process failed, timed out, or was truncated on every attempt "
             f"(after {MAX_IMPLEMENTER_PROCESS_ATTEMPTS} tries) — see logs/model_calls.jsonl"],
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
            if not run_norm_implementer_with_retry(round_number, extra_message=repair_message):
                discard_norm_implementation(
                    round_number,
                    [f"norm-implementer's repair run failed, timed out, or was truncated on every "
                     f"attempt (after {MAX_IMPLEMENTER_PROCESS_ATTEMPTS} tries) — see "
                     f"logs/model_calls.jsonl"],
                )
                return False
            continue

        evaluation = None
        evaluator_message = None
        for eval_attempt in range(1, MAX_EVALUATOR_ATTEMPTS + 1):
            refresh_knowledge_graph(round_number)
            evaluation = run_norm_evaluator(round_number, extra_message=evaluator_message)
            if evaluation is not None:
                break
            print(f"Round {round_number}: norm-evaluator itself produced no usable verdict "
                  f"(attempt {eval_attempt}/{MAX_EVALUATOR_ATTEMPTS}) — retrying the evaluator, "
                  f"not the implementation, since this doesn't say anything about whether the "
                  f"code is actually correct.")
            # A fresh, stateless retry each time — the message must not
            # imply the model has any memory of a "previous response".
            evaluator_message = (
                f"This is a fresh, independent evaluation attempt for round {round_number}. "
                "You have no memory of any earlier attempt — there is no 'previous response' "
                "for you to reference, recall, or assume was correct, and nothing about an "
                "earlier attempt (including whether it was missing a sentinel line) tells you "
                "anything about whether this round is actually compliant. Do the full "
                "evaluation from scratch: read norm.txt and "
                f"state/norm_specs/round_{round_number}.md and the diff, write and run your own "
                "tests, then reach a verdict based only on what you observe this time. End your "
                "response with EVALUATION_RESULT: COMPLIANT or EVALUATION_RESULT: NEEDS_REPAIR, "
                "in exactly that form."
            )
        if evaluation is None:
            discard_norm_implementation(
                round_number,
                [f"norm-evaluator failed to produce a parseable verdict after "
                 f"{MAX_EVALUATOR_ATTEMPTS} attempts — see logs/model_calls.jsonl"],
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
        if not run_norm_implementer_with_retry(round_number, extra_message=repair_message):
            discard_norm_implementation(
                round_number,
                [f"norm-implementer's repair run failed, timed out, or was truncated on every "
                 f"attempt (after {MAX_IMPLEMENTER_PROCESS_ATTEMPTS} tries) — see "
                 f"logs/model_calls.jsonl"],
            )
            return False

    return False  # unreachable — the loop above always returns first


ROUND_ARTIFACT_PATHS = [
    "logs",
    "norm.txt",
    "plots",
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
    discard_norm_implementation() may `git clean -fd`, and logs/norm.txt
    are exactly the forensic record of *why* a round was discarded — they
    must never be at risk of being wiped by the discard they explain."""
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
    this, a norm-implementer edit to roles/*.py, norms/*.py,
    actions/handlers/*.py, or objects/handlers/*.py never takes effect
    within a single continuous run. engine.norms.registry's NORM_TYPES is
    computed once at first import, so reloading norms/*.py alone doesn't
    re-scan it — reload order matters: roles/norms first, then
    engine.norms.registry (rebinds NORM_TYPES), then engine.norms.engine
    (rebinds its own import of load_norms), then actions/objects (rebinds
    their own imports).

    engine/institution/*.py itself is deliberately never reloaded here —
    it's off-limits to the norm-implementer by construction (nothing in
    it is on any tracked-path list), so nothing there can change mid-run.
    Action/object *handler* resolution (engine.institution.runtime.
    resolve_handler(), ObjectRuntime.custom()'s discover_handlers() call)
    is always a fresh importlib.import_module() rather than an
    eagerly-cached registry, precisely so those two pluggable kinds don't
    need their own equivalent of NORM_TYPES's re-scan step — reloading
    actions.handlers.*/objects.handlers.* below is enough on its own."""
    for prefix in ("roles", "norms"):
        for name in sorted(n for n in list(sys.modules) if n == prefix or n.startswith(prefix + ".")):
            importlib.reload(sys.modules[name])
    for module_name in ("engine.norms.registry", "engine.norms.engine"):
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
    for prefix in ("actions", "objects"):
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
