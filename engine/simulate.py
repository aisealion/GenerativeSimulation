#!/usr/bin/env python3
import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from engine.call_log import log_call
from engine.clarify_norm import ask_norm_proposer
from engine.llm_agents import call_norm_architect_agent, call_norm_auditor_agent
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
# norm-architect's and norm-auditor's own (ops/logs/norm_architect.jsonl /
# norm_auditor.jsonl) are now written directly from
# engine.llm_agents.call_norm_architect_agent()/call_norm_auditor_agent()
# instead of from here — see that module's own NORM_ARCHITECT_LOG_PATH /
# NORM_AUDITOR_LOG_PATH — since they're plain completion calls now, not
# opencode subprocesses this file drives.
NORM_ENGINEER_LOG_PATH = ROOT / "ops" / "logs" / "norm_engineer.jsonl"
COLLAPSE_THRESHOLD_KG = 0
DEFAULT_MAX_ROUNDS = 100

# Everything a norm round is allowed to touch, across both norm-architect
# (tests/norm_checks only) and norm-engineer (everything else here).
# Staged (git add) by stage_norm_implementation() and reverted (git
# checkout/clean) by discard_norm_implementation() on a discard.
NORM_ROUND_TRACKED_PATHS = [
    # state/runtime.json is never here — simulation-owned, never a norm
    # round's to write; kept off so a discard's `git clean -fd` can never
    # touch it. state/schedule.json is ALSO never here any more, for the
    # same reason, one level removed: it's now a COMPILED artifact
    # (engine.institution.scheduler.compile_schedule(), rebuilt every
    # round from state/actions/*.json's own scheduling.after/before)
    # rather than something hand-edited — see ROUND_ARTIFACT_PATHS below.
    # "actions" covers both actions/handlers/*.py AND
    # actions/rules/{action_name}/*.py — rule plugins moved under actions/
    # entirely (no more standalone top-level norms/ directory) since a
    # rule is always about one specific action.
    "actions",
    "objects",
    "prompts",
    # norm-architect's pre-implementation tests (written before
    # norm-engineer runs at all) for this round's rule/action changes.
    # tests/norm_evaluation is NOT here — norm-auditor stopped writing its
    # own independent test suite there on 2026-09-23; it's a plain
    # completion call now that cross-references norm.txt against the
    # diff directly (see call_norm_auditor_agent() in engine/llm_agents.py).
    "tests/norm_checks",
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
    # 2026-09-24: _gather_norm_evidence()'s own output — the structured,
    # per-requirement package norm-auditor reads instead of a raw diff.
    # Harness-generated (not written by any LLM call), but still needs to
    # revert on a discard like everything else the round produced.
    "state/norm_evidence",
    # Editable so an edit here is actually staged and syntax-checked.
    "engine/simulate.py",
]

# A narrower view of the above, used ONLY by
# norm_implementation_no_code_changes_errors() — "tests/norm_checks" is
# excluded here because norm-architect writes there *before*
# norm-engineer ever runs, so it's already dirty by the time that check
# executes; "state/norm_evidence" is excluded for the same reason one
# level later — _gather_norm_evidence() itself only runs after this check
# already has, but excluding it here keeps this list's own meaning
# consistent ("norm-engineer's own code changes"), not because it would
# otherwise cause a false negative. Using the full NORM_ROUND_TRACKED_PATHS
# list here would let a norm-engineer that touched nothing at all slip
# past undetected, since the architect's own pre-existing test files
# would already satisfy a bare "is anything dirty" check. Every other use
# of the tracked-paths list (compile-checking, discard, staging)
# intentionally keeps using the full list — everything must still be
# revertible on discard and compile-checked regardless of who authored it.
NORM_ENGINEER_CODE_PATHS = [
    p for p in NORM_ROUND_TRACKED_PATHS if p not in ("tests/norm_checks", "state/norm_evidence")
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
    hand-edited, so a norm round that added or reordered an
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
    stream parse_opencode_jsonl() reads — feeds ops/logs/norm_architect.jsonl
    / ops/logs/norm_engineer.jsonl / ops/logs/norm_auditor.jsonl. A tool named "invalid" means the model
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
    """Returns "stop" if the stream's last real content event is a "text"
    event (the model's last action was producing its final response, not
    calling a tool — a genuine, deliberate end of turn), "tool-calls" if
    it's a "tool_use" event instead (the session ended right after a tool
    call, with no follow-up turn at all — a real truncation), the last
    step_finish event's own `reason` field as a fallback if neither a
    "text" nor a "tool_use" event ever appeared at all (an empty/failed
    completion — see below), or None on parse failure / a totally empty
    stream. See run_norm_engineer()'s use of this.

    2026-09-24 fix: previously returned the `reason` field off the LAST
    step_finish event, full stop. That broke completely under opencode
    v2: a real 5-attempt round showed EVERY attempt's step_finish events
    saying "tool-calls" and nothing else — even attempts whose actual
    final event was a complete, well-formed text response ending in a
    valid fenced ```json report block. v2 evidently doesn't emit a
    closing step_finish/reason:"stop" event after a text-only final turn
    the way v1 did, so the old logic always fell back to the
    second-to-last (tool-related) step_finish and misclassified every
    genuinely-complete session as truncated — discarding real, correct
    work after exhausting the full retry budget, round after round.
    Checking the actual last content event's own type instead sidesteps
    this entirely — it doesn't depend on whether a terminal step_finish
    ever arrives.

    The original empty-completion signature this function also existed to
    catch ("unknown" paired with all-zero token counts — 6 of 26 real
    invocations on an early 12-round run, the underlying model completion
    itself silently failing or returning empty) never has ANY text or
    tool_use event to inspect in the first place, so it still falls
    through to the old step_finish-reason lookup as a fallback — this fix
    only changes behavior for streams that ended with real content."""
    last_reason = None
    last_content_type = None
    try:
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            event_type = event.get("type")
            if event_type == "step_finish":
                last_reason = event.get("part", {}).get("reason")
            elif event_type in ("text", "tool_use"):
                last_content_type = event_type
    except (json.JSONDecodeError, AttributeError):
        return None
    if last_content_type == "text":
        return "stop"
    if last_content_type == "tool_use":
        return "tool-calls"
    return last_reason


def extract_session_id(stdout):
    """First sessionID found anywhere in the opencode run --format json
    JSONL stream (every event in one session carries the same id). Used
    only by run_norm_engineer_with_retry()'s and run_norm_architect_with_retry()'s
    own bounded 2-attempt session pairing (2026-09-18) — unlike the 2026-09-15 feature this
    reintroduces a narrow slice of (reverted 2026-09-17 after it caused a
    real multi-hour collapse from unbounded cross-call growth), this
    never threads a session id past a single pair of attempts, so it
    can't reproduce that failure mode. Returns None on any parse failure
    or if no event carries one."""
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


AUDIT_PASSED_RE = re.compile(r"\bAUDIT_PASSED\b", re.IGNORECASE)


def extract_audit_result(text):
    """Finds the literal AUDIT_PASSED sentinel anywhere in the response —
    norm-auditor's own standing instructions (NORM_AUDITOR_SYSTEM_PROMPT,
    engine/llm_agents.py) say to output exactly this phrase, on its own
    line, as the last thing in its response, iff the code fully satisfies
    the norm with no under-enforcement — and to end with a specific
    description of the gap instead, never this phrase, otherwise. Returns
    "COMPLIANT" or "NEEDS_REPAIR" — never None: unlike the older two-
    keyword AUDIT_RESULT: COMPLIANT|NEEDS_REPAIR sentinel this replaces,
    there's no separate "well-formed but says nothing" state to detect
    here — any response missing the pass phrase is, by construction,
    NEEDS_REPAIR, the same never-silently-coerced-to-a-pass stance that
    convention already had."""
    return "COMPLIANT" if AUDIT_PASSED_RE.search(text) else "NEEDS_REPAIR"


def clear_stale_opencode_snapshot_lock():
    """opencode keeps its own filesystem-snapshot history (used for its
    interactive undo/revert feature) in a separate bare git repo under
    ~/.local/share/opencode/snapshot/<project-hash>/<tracking-hash>/ — a
    completely different repo from this project's own .git/, and one this
    headless pipeline never actually reads from (nobody is present to
    invoke "undo"). A real job's opencode.log showed this repo's own
    index.lock stuck ("fatal: Unable to create '.../index.lock': File
    exists... a git process may have crashed") across every session for
    hours, on multiple unrelated jobs — plausible root cause: this
    project's own subprocess.run(..., timeout=3600) kills only the direct
    opencode process on a timeout, not any child `git` process opencode
    itself may have spawned for its own snapshot bookkeeping; a `git`
    process killed between creating and releasing its lock leaves that
    lock file orphaned forever, since nothing else ever removes it.

    Safe to clear unconditionally right before every opencode invocation:
    this project never runs two opencode processes concurrently (every
    call here is a single blocking subprocess.run()), so any index.lock
    found at the moment a new call is about to start cannot belong to a
    still-legitimately-running process — exactly the same reasoning
    already applied to CodeGraph's own per-round `unlock` in
    refresh_codegraph_index(). Best-effort: a permissions error or a
    missing directory is not worth failing a round over."""
    snapshot_root = Path.home() / ".local" / "share" / "opencode" / "snapshot"
    if not snapshot_root.is_dir():
        return
    try:
        for lock_path in snapshot_root.rglob("index.lock"):
            try:
                lock_path.unlink()
                print(f"Cleared a stale opencode snapshot lock: {lock_path}")
            except OSError:
                pass
    except OSError:
        pass


def _norm_architect_context_bundle():
    """The fixed reference bundle handed to norm-architect in place of the
    tool-based exploration it used to do (codegraph_explore, selective doc
    reads) — see call_norm_architect_agent() in engine/llm_agents.py for
    why it has no tools at all any more. Assembled fresh every call so it
    always reflects the current on-disk institution, never cached.

    2026-09-24: trimmed to architecture.md ONLY — action-contract.md/
    rule-contract.md/object-contract.md/role-contract.md/state-files.md
    are deliberately excluded now. Those are field-level IMPLEMENTATION
    contracts (JSON spec shapes, Python hook signatures, exact state file
    paths) — exactly the "which file, which Python shape" decisions
    norm-architect no longer makes at all (semantic compilation only; see
    NORM_ARCHITECT_SYSTEM_PROMPT). architecture.md alone is the
    "conceptual model" doc — it teaches the actual ROLE/ACTION/OBJECT/
    RULE distinctions without naming a single file path for norm-architect
    to (necessarily incorrectly) guess at. norm-engineer still gets all
    six contracts, unchanged, via its own opencode read/glob tools."""
    parts = []

    institution_path = ROOT / "state" / "institution.json"
    if institution_path.is_file():
        parts.append(
            "### state/institution.json (the current structural catalog — check "
            "here before saying a requirement needs a brand new concept)\n```json\n"
            f"{institution_path.read_text().strip()}\n```"
        )

    doc_path = ROOT / "docs" / "institution-contracts" / "architecture.md"
    if doc_path.is_file():
        parts.append(f"### docs/institution-contracts/architecture.md\n{doc_path.read_text().strip()}")

    return "\n\n".join(parts)


VALID_NORM_PLAN_REQUIREMENT_TYPES = {"ROLE", "ACTION", "OBJECT", "RULE", "VISIBILITY", "LIFECYCLE", "UNRESOLVED"}
# Types where a fisher's actual experience changes — every requirement of
# one of these types needs at least one acceptance test, per
# validate_norm_plan() below. OBJECT (pure inventory, no decision) and
# LIFECYCLE (a duration attached to something else already tested) are
# deliberately excluded — see architecture.md's own "inventory vs.
# decision vs. rule" distinction.
NORM_PLAN_TYPES_REQUIRING_TESTS = {"ROLE", "ACTION", "RULE", "VISIBILITY"}


def validate_norm_plan(plan):
    """The deterministic Harness Validator — pure Python, no LLM call,
    sitting between norm-architect and norm-engineer. Catches structural
    incompleteness (a missing field, a dangling reference, a requirement
    nobody wrote a test for) before an expensive opencode session ever
    starts, the same "cheap check first" reasoning behind every other
    norm_implementation_*_errors() function in this file. Returns a list
    of human-readable problem strings (empty if the plan is structurally
    sound) — never judges whether the plan is semantically RIGHT, only
    whether it's complete enough for norm-engineer to act on."""
    errors = []
    requirements = plan.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        return ["\"requirements\" must be a non-empty list"]

    seen_ids = set()
    for i, req in enumerate(requirements):
        label = f"requirements[{i}]"
        req_id = req.get("id")
        if not req_id:
            errors.append(f"{label} has no \"id\"")
            continue
        label = f"requirement {req_id!r}"
        if req_id in seen_ids:
            errors.append(f"{label}: duplicate id — every requirement needs a unique id")
        seen_ids.add(req_id)

        req_type = req.get("type")
        if req_type not in VALID_NORM_PLAN_REQUIREMENT_TYPES:
            errors.append(
                f"{label}: \"type\" is {req_type!r}, must be one of "
                f"{sorted(VALID_NORM_PLAN_REQUIREMENT_TYPES)}"
            )
            continue
        if req_type == "UNRESOLVED":
            if not req.get("reason"):
                errors.append(f"{label}: type UNRESOLVED needs a \"reason\" field")
            continue
        if not req.get("description"):
            errors.append(f"{label}: missing \"description\"")

        if req_type in ("ROLE", "ACTION", "RULE", "VISIBILITY") and not req.get("agent_experience"):
            errors.append(
                f"{label}: type {req_type} needs an \"agent_experience\" block — what does a "
                f"fisher actually know/decide/may-do/may-not-do/remember/observe because of this?"
            )

    acceptance_tests = plan.get("acceptance_tests") or []
    tested_requirement_ids = set()
    for i, test in enumerate(acceptance_tests):
        label = f"acceptance_tests[{i}]"
        test_req = test.get("requirement")
        if not test_req:
            errors.append(f"{label} has no \"requirement\"")
            continue
        if test_req not in seen_ids:
            errors.append(f"{label}: \"requirement\" {test_req!r} doesn't match any requirement id")
            continue
        tested_requirement_ids.add(test_req)
        if not test.get("scenario"):
            errors.append(f"{label} (requirement {test_req!r}): missing \"scenario\"")
        for field in ("given", "when", "expect"):
            # Presence, not truthiness — an empty {} is a legitimate "no
            # preconditions" scenario, not a missing field.
            if field not in test:
                errors.append(f"{label} (requirement {test_req!r}): missing \"{field}\"")

    for req in requirements:
        req_id = req.get("id")
        if req_id and req.get("type") in NORM_PLAN_TYPES_REQUIRING_TESTS and req_id not in tested_requirement_ids:
            errors.append(
                f"requirement {req_id!r} (type {req.get('type')}) has no acceptance_tests entry "
                f"referencing it — every requirement that changes what a fisher experiences needs "
                f"at least one given/when/expect scenario"
            )

    for i, critique in enumerate(plan.get("open_critiques") or []):
        critique_req = critique.get("requirement")
        if critique_req and critique_req not in seen_ids:
            errors.append(
                f"open_critiques[{i}]: \"requirement\" {critique_req!r} doesn't match any requirement id"
            )
        if not critique.get("critique_question"):
            errors.append(f"open_critiques[{i}]: missing \"critique_question\"")

    return errors


def _extract_fenced_block(text, lang):
    """Last fenced ```<lang> block in text, scanning from the end — same
    "don't get fooled by an earlier example block" reasoning as
    extract_json_report(). Returns None if none found."""
    matches = re.findall(rf"```{lang}\s*\n(.*?)```", text, re.DOTALL)
    return matches[-1].strip() if matches else None


MAX_NORM_CLARIFICATIONS_PER_ROUND = 5


def run_norm_architect(round_number):
    """Runs norm-architect as a direct, tool-free litellm completion (see
    call_norm_architect_agent() in engine/llm_agents.py for why it stopped
    running through opencode) and writes its plan to disk itself, since
    the model has no write tool of its own any more. Returns
    (success, plan) — plan is the parsed norm_plan json (requirements +
    acceptance_tests) on success, None otherwise.

    2026-09-24: no longer extracts or writes a Python test file at all —
    norm-architect writes acceptance-test SPECIFICATIONS
    (given/when/expect), and norm-engineer (which actually has repo
    access and understands fixtures/ActionContext) translates those into
    real pytest as its own first implementation step. See
    NORM_ARCHITECT_SYSTEM_PROMPT for why, and render_engineer_kickoff()
    for the handoff.

    A second, finalizing completion call happens if the first pass either
    reported open_critiques (resolved via ask_norm_proposer(), same as
    before) or if validate_norm_plan() — the deterministic Harness
    Validator, no LLM call — found structural problems (a missing
    agent_experience block, a requirement with no acceptance test, a
    dangling reference). Both fold into the SAME second pass, one bounded
    extra call, not two separate retry loops. If the plan is still
    structurally invalid after that second pass, this is a real design
    failure, not a process hiccup: return (False, None) and let the round
    be discarded, same contract as every other failure path here."""
    norm_path = ROOT / "norm.txt"
    if not norm_path.is_file():
        print(f"Round {round_number}: norm.txt is missing — nothing for norm-architect to "
              f"design against.", file=sys.stderr)
        return False, None
    norm_text = norm_path.read_text()
    context_bundle = _norm_architect_context_bundle()

    print("\n--- invoking norm-architect ---")
    raw_text = call_norm_architect_agent(round_number, norm_text, context_bundle)
    if raw_text is None:
        return False, None

    plan_raw = _extract_fenced_block(raw_text, "json")
    try:
        plan = json.loads(plan_raw) if plan_raw else None
    except json.JSONDecodeError:
        plan = None

    if plan is None or "requirements" not in plan:
        print(f"Round {round_number}: norm-architect's response never contained a parseable "
              f"```json block with a \"requirements\" key — treating this round's design as "
              f"failed.", file=sys.stderr)
        return False, None

    open_critiques = plan.get("open_critiques") or []
    validator_errors = validate_norm_plan(plan)

    if open_critiques or validator_errors:
        resolutions = []
        budget = min(len(open_critiques), MAX_NORM_CLARIFICATIONS_PER_ROUND)
        if budget < len(open_critiques):
            print(f"Round {round_number}: norm-architect raised {len(open_critiques)} open "
                  f"critiques but the round's shared clarification budget only allows "
                  f"{budget} — resolving the first {budget}, the rest stay unresolved "
                  f"(reflected as-is in the plan this round proceeds with).")
        for critique in open_critiques[:budget]:
            question = critique.get("critique_question")
            if not question:
                continue
            try:
                answer = ask_norm_proposer(round_number, question)
            except RuntimeError as exc:
                print(f"Round {round_number}: couldn't resolve a norm-architect critique "
                      f"({exc}) — proceeding with the first pass's own best-effort reading.",
                      file=sys.stderr)
                continue
            resolutions.append({
                "critique_question": question,
                "answer": answer.get("answer", answer),
            })

        if validator_errors:
            print(f"Round {round_number}: the harness found {len(validator_errors)} structural "
                  f"problem(s) in norm-architect's plan — asking it to fix them.")
        if resolutions:
            print(f"Round {round_number}: resolved {len(resolutions)} norm-architect "
                  f"critique(s) — asking it to finalize.")

        if resolutions or validator_errors:
            final_text = call_norm_architect_agent(
                round_number, norm_text, context_bundle,
                resolutions=resolutions or None, validator_errors=validator_errors or None,
            )
            if final_text is not None:
                final_plan_raw = _extract_fenced_block(final_text, "json")
                try:
                    final_plan = json.loads(final_plan_raw) if final_plan_raw else None
                except json.JSONDecodeError:
                    final_plan = None
                if final_plan is not None and "requirements" in final_plan:
                    plan = final_plan
                    validator_errors = validate_norm_plan(plan)
                else:
                    print(f"Round {round_number}: norm-architect's finalizing pass didn't "
                          f"produce a parseable plan — keeping the first pass's own output.",
                          file=sys.stderr)

    if validator_errors:
        print(f"Round {round_number}: norm-architect's plan is still structurally invalid after "
              f"its finalizing pass — treating this round's design as failed:\n"
              + "\n".join(f"  - {e}" for e in validator_errors), file=sys.stderr)
        return False, None

    tests_dir = ROOT / "tests" / "norm_checks" / f"round_{round_number}"
    tests_dir.mkdir(parents=True, exist_ok=True)
    plan_path = tests_dir / "norm_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")

    print(f"Round {round_number}: norm-architect wrote {plan_path.relative_to(ROOT)} "
          f"({len(plan['requirements'])} requirement(s), "
          f"{len(plan.get('acceptance_tests') or [])} acceptance test(s)).")
    return True, plan


def render_engineer_kickoff(norm_plan, round_number):
    """Serializes norm-architect's FULL plan — every requirement and every
    acceptance test it wrote, not a trimmed summary — into norm-engineer's
    kickoff message. This is the entire handoff: norm-engineer never
    re-reads norm.txt's own reasoning path, only this plan, so nothing
    here can be assumed "the engineer already knows from before."

    2026-09-24: norm-architect no longer writes Python at all (see
    run_norm_architect()) — only given/when/expect acceptance-test
    SPECIFICATIONS. norm-engineer's job now explicitly starts with
    translating those into a real pytest file, using the exact
    test_{requirement_id}_{scenario} naming convention
    _gather_norm_evidence() depends on to map pass/fail back to a
    requirement — *then* implementing until that suite passes. The
    given/when/expect values themselves are frozen at norm-architect time
    and must be asserted against literally, not reinvented — the one
    deliberate self-grading guardrail this handoff still has, now that
    the same agent authors both the tests and the implementation (see
    _gather_norm_evidence()'s literal-value grep for the other half of
    this guardrail, and norm-auditor's own independent read of raw
    norm.txt for the real backstop)."""
    tests_dir = f"tests/norm_checks/round_{round_number}/"
    test_path = f"{tests_dir}test_round_{round_number}.py"
    return (
        f"This is round {round_number}. norm-architect has designed every requirement and "
        f"written acceptance-test specifications (no Python — plain given/when/expect facts). "
        f"Below is its complete plan, verbatim; treat it as the full specification, not a "
        f"summary to re-derive from norm.txt yourself:\n\n"
        f"```json\n{json.dumps(norm_plan, indent=2)}\n```\n\n"
        f"Your job, in order:\n"
        f"1. Translate every entry in \"acceptance_tests\" into a real pytest test function "
        f"in exactly {test_path} — name each one test_{{requirement}}_{{scenario}} (e.g. "
        f"\"requirement\": \"R2\", \"scenario\": \"compliant_decision\" becomes "
        f"test_R2_compliant_decision) so the given/expect values you assert against are the "
        f"literal ones in the plan above, never invented or loosened. Build the fabricated "
        f"state realistically through the real handler/rule/action machinery, following "
        f"docs/institution-contracts/. It must fail red first — nothing implementing this "
        f"round's norm exists yet.\n"
        f"2. Implement every requirement, routing each by its \"type\" (ROLE/ACTION/OBJECT/"
        f"RULE/VISIBILITY/LIFECYCLE) through the matching docs/institution-recipes/ entry, "
        f"until {tests_dir} passes. Every ROLE/ACTION/RULE/VISIBILITY requirement's own "
        f"\"agent_experience\" block is a real requirement, not decoration — a fisher must "
        f"actually come to know/decide/may-do/remember/observe what it says, not just have it "
        f"computed in Python.\n\n"
        f"Once done, dispatch norm-finalizer with this same plan forwarded verbatim. End your "
        f"response with the fenced ```json report block your instructions describe (the one "
        f"containing a \"spec_path\" key) — this is required every time, not just when "
        f"something went wrong."
    )


def run_norm_engineer(round_number, extra_message=None, session_id=None):
    """Runs the norm-engineer as an opencode subprocess. Returns
    (success, session_id) — success is True on a clean (returncode 0) run
    that also ended on a genuine "stop" (see extract_last_step_reason()),
    False on any failure — a timeout, a crash, a non-zero exit, or a
    session that was silently truncated mid-task despite exiting 0.
    Analyzing a real 12-round run (back when this agent also did its own
    design reasoning, before the norm-architect split) found the
    truncated-session case common (13 of 26 real invocations never
    reached a deliberate stop) and very likely why code-writing
    specifically (which tended to happen only after exploration/spec-
    writing) so rarely got reached at all. The caller treats a False
    success like a compile error: discard this round's changes and
    continue, rather than crashing the whole multi-round run or trusting
    partial work as if it were final.

    session_id, when given, is passed to opencode as `--session <id>` so
    this call continues that existing session instead of starting a fresh
    one. The returned session_id is always the real id opencode actually
    used (extracted from this call's own output, falling back to whatever
    was passed in if extraction fails). Unbounded cross-call session
    continuation was tried (2026-09-15) and reverted (2026-09-17) after a
    real round showed the actual failure mode it introduces: one
    continuously-growing session across ~15 calls and ~6 hours eventually
    became too large for the model to even begin responding to within
    opencode's own internal provider-header timeout, burning the round's
    entire process-retry budget on calls that could never have succeeded.
    This function itself doesn't bound anything — it's
    run_norm_engineer_with_retry()'s own pairing logic (2026-09-18)
    that caps how far a session_id it discovers is ever threaded forward,
    specifically to get the "don't re-read everything from scratch on an
    immediate retry" benefit without reproducing that unbounded growth."""
    clear_stale_opencode_snapshot_lock()
    print("\n--- invoking norm-engineer ---")
    # The orchestrator always supplies extra_message (render_engineer_kickoff()
    # on the first call, a repair message on every later one) — this
    # fallback only matters for a direct/test call that omits it.
    message = extra_message or (
        f"This is round {round_number}. Read the requirements checklist norm-architect "
        f"left you and the failing tests under tests/norm_checks/round_{round_number}/, "
        f"then implement accordingly, following your standing instructions. End your "
        f"response with the fenced ```json report block your instructions describe "
        f"(the one containing a \"spec_path\" key) — this is required every time, not "
        f"just when something went wrong."
    )
    # --auto: (2026-09-15) — a real run's own logs showed this agent
    # hallucinating a slightly-wrong absolute path on a read/edit call (a
    # doubled letter, a typo'd username) often enough to matter;
    # opencode's external_directory permission defaults to "ask", and with
    # nobody present to answer in this headless subprocess it silently
    # auto-denies — the session then ends abnormally mid-tool-call rather
    # than recovering, which is a real share of why a round needs so many
    # process retries. --auto only auto-approves what isn't explicitly
    # denied, so the actual `permission.edit`/`permission.bash`/
    # `permission.read` denies this agent already has (ops/, cache dirs,
    # protected paths, tests/norm_checks/*, etc.) are unaffected.
    cmd = ["opencode", "run", "--agent", "norm-engineer", "--format", "json", "--auto"]
    # --session: continue an existing session instead of starting fresh —
    # only when the caller actually has one. run_norm_engineer_with_retry()
    # is the only caller that ever passes one, and only within its own
    # bounded 2-attempt pairing (2026-09-18) — see this function's own
    # docstring for why unbounded continuation isn't repeated here.
    if session_id:
        cmd += ["--session", session_id]
    model = (
        os.environ.get("NORM_ENGINEER_MODEL")
        or os.environ.get("NORM_IMPLEMENTER_MODEL")  # transition fallback, pre-split env var
        or os.environ.get("OPENCODE_MODEL")
    )
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
        print(f"Round {round_number}: norm-engineer didn't finish within 3600s — "
              f"treating this round's norm implementation as failed, not crashing the run.",
              file=sys.stderr)
        log_call(
            also_log_to=NORM_ENGINEER_LOG_PATH,
            call="norm_engineer", agent_id=None, round=round_number, action=None,
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
    report = extract_json_report(final_text, required_keys={"spec_path"})
    # The real id opencode used this call — falls back to whatever was
    # passed in if this call's own output doesn't parse for some reason.
    new_session_id = extract_session_id(result.stdout) or session_id

    # A session that ended abnormally (see extract_last_step_reason()'s own
    # docstring for the two real truncation signatures this catches) is not
    # trustworthy even though opencode itself exited 0 — the model was cut
    # off mid-task, not finished. Checked here, not just logged, since a
    # returncode-0 check alone can't tell the two apart.
    truncated = result.returncode == 0 and last_step_reason not in (None, "stop")

    log_call(
        also_log_to=NORM_ENGINEER_LOG_PATH,
        call="norm_engineer",
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
        print(f"Round {round_number}: norm-engineer exited with code {result.returncode} — "
              f"treating this round's norm implementation as failed, not crashing the run.",
              file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return False, new_session_id
    if truncated:
        print(f"Round {round_number}: norm-engineer's session ended abnormally (last step "
              f"reason: {last_step_reason!r}, not a genuine 'stop') — likely a failed or "
              f"truncated completion call, not a deliberate finish. Treating this round's "
              f"partial work as failed rather than trusting it.", file=sys.stderr)
        return False, new_session_id
    return True, new_session_id


def _gather_norm_evidence(round_number, plan):
    """Assembles the structured per-requirement evidence package
    norm-auditor reviews instead of a raw diff (2026-09-24, by request) —
    "does this evidence demonstrate the norm was actually instantiated?"
    is a task DeepSeek-R1 is much better suited to than "does this diff
    look right?". Composed from two independently-verified sources,
    reusing existing machinery rather than reinventing either:

    1. Structural evidence: norm-finalizer's own requirement_evidence
       claims from state/norm_specs/round_{N}.md's trailing json block —
       norm-finalizer already independently verifies these itself (see
       its own "Verify, don't transcribe" step) before writing them, the
       same verify-don't-trust pattern
       norm_implementation_unverified_requirements_errors() already reads
       from that same file for a different purpose.
    2. Acceptance-test evidence: runs tests/norm_checks/round_{N}/ once
       with --junit-xml (a built-in pytest flag — no new dependency,
       unlike a json-report plugin) and parses per-test pass/fail from
       the XML via the stdlib's xml.etree.ElementTree, matching each
       test_{id}_{scenario} function back to its requirement id.

    Also runs the one structural self-grading guardrail this handoff
    still has (see render_engineer_kickoff()'s own docstring): a grep of
    the generated test file for each acceptance test's literal
    given/expect values, noted as evidence either way — flagged, not
    blocking, since norm-auditor's own independent read of raw norm.txt
    is the real backstop.

    Written to state/norm_evidence/round_{N}.json and returned."""
    evidence = {req["id"]: [] for req in plan.get("requirements", []) if req.get("id")}

    spec_path = ROOT / "state" / "norm_specs" / f"round_{round_number}.md"
    if spec_path.is_file():
        spec_report = extract_json_report(spec_path.read_text(), required_keys={"requirement_evidence"})
        if spec_report:
            for req_id, claims in (spec_report.get("requirement_evidence") or {}).items():
                evidence.setdefault(req_id, []).extend(claims)

    tests_dir = ROOT / "tests" / "norm_checks" / f"round_{round_number}"
    test_path = tests_dir / f"test_round_{round_number}.py"
    if not test_path.is_file():
        for req_id in evidence:
            evidence[req_id].append(
                f"no {test_path.relative_to(ROOT)} file was ever written — no acceptance tests to run"
            )
        evidence_dir = ROOT / "state" / "norm_evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / f"round_{round_number}.json").write_text(json.dumps(evidence, indent=2) + "\n")
        return evidence

    with tempfile.TemporaryDirectory() as tmp_dir:
        junit_path = Path(tmp_dir) / "results.xml"
        subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dir), f"--junit-xml={junit_path}", "-q"],
            cwd=ROOT, capture_output=True, text=True, timeout=300,
        )
        if junit_path.is_file():
            try:
                testcases = list(ET.parse(junit_path).getroot().iter("testcase"))
            except ET.ParseError:
                testcases = []
            for testcase in testcases:
                test_name = testcase.get("name") or ""
                req_id = next((r for r in evidence if test_name.startswith(f"test_{r}_")), None)
                if req_id is None:
                    continue
                failure = testcase.find("failure")
                error = testcase.find("error")
                if failure is not None:
                    evidence[req_id].append(
                        f"acceptance test {test_name}: FAIL — {(failure.get('message') or '').strip()}"
                    )
                elif error is not None:
                    evidence[req_id].append(
                        f"acceptance test {test_name}: ERROR — {(error.get('message') or '').strip()}"
                    )
                else:
                    evidence[req_id].append(f"acceptance test {test_name}: PASS")

    test_source = test_path.read_text()
    for acceptance_test in plan.get("acceptance_tests") or []:
        req_id = acceptance_test.get("requirement")
        if req_id not in evidence:
            continue
        literal_values = [
            str(v) for section in ("given", "when", "expect")
            for v in (acceptance_test.get(section) or {}).values()
        ]
        missing = [v for v in literal_values if v and str(v) not in test_source]
        if missing:
            evidence[req_id].append(
                f"self-grading guardrail: the generated test for scenario "
                f"{acceptance_test.get('scenario')!r} doesn't reference the plan's own literal "
                f"value(s) {missing} — norm-engineer may have loosened or reinterpreted the spec "
                f"rather than asserting it literally"
            )

    evidence_dir = ROOT / "state" / "norm_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / f"round_{round_number}.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence


def run_norm_auditor(round_number):
    """Audits this round's norm-engineer changes against the raw norm
    text — a clean model instance that never wrote the code it's
    reviewing (see call_norm_auditor_agent() in engine/llm_agents.py for
    why this is a plain completion call, not an opencode agent, as of
    2026-09-23). Returns {"result": "COMPLIANT" | "NEEDS_REPAIR", "text":
    final_text} on a completed call, or None if the call itself failed
    after exhausting its own retry budget (MAX_AUDITOR_ATTEMPTS, inside
    that function) — treated by the caller like a norm-engineer failure:
    discard, don't crash the rest of the run.

    Always a fresh completion call, never any shared session/context with
    whatever call wrote the code — the actual mechanism behind "never let
    the model that wrote the code approve its own work."

    2026-09-24: reads norm-architect's frozen plan back off disk itself
    (the same self-contained pattern this function already used for
    norm.txt) and calls _gather_norm_evidence() to assemble the structured
    evidence package — replacing the old raw git-diff payload."""
    print("\n--- invoking norm-auditor ---")
    norm_path = ROOT / "norm.txt"
    if not norm_path.is_file():
        print(f"Round {round_number}: norm.txt is missing — nothing for norm-auditor to "
              f"audit against.", file=sys.stderr)
        return None
    norm_text = norm_path.read_text()

    plan_path = ROOT / "tests" / "norm_checks" / f"round_{round_number}" / "norm_plan.json"
    if not plan_path.is_file():
        print(f"Round {round_number}: {plan_path.relative_to(ROOT)} is missing — nothing for "
              f"norm-auditor to audit against.", file=sys.stderr)
        return None
    try:
        plan = json.loads(plan_path.read_text())
    except json.JSONDecodeError as exc:
        print(f"Round {round_number}: {plan_path.relative_to(ROOT)} isn't valid JSON ({exc}) — "
              f"treating this audit as failed.", file=sys.stderr)
        return None

    evidence = _gather_norm_evidence(round_number, plan)

    raw_text = call_norm_auditor_agent(round_number, norm_text, plan, evidence)
    if raw_text is None:
        return None

    verdict = extract_audit_result(raw_text)
    print(raw_text)
    return {"result": verdict, "text": raw_text}


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
    for tracked in NORM_ROUND_TRACKED_PATHS:
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
    return [f"norm-engineer touched protected path(s), never allowed:\n{touched}"]


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
    """Catches a norm-engineer round that creates a new
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
    what it actually found (not what norm-engineer merely claimed)
    in that same file's own trailing json block, as
    "verification_failures" — but until this check, nothing in the
    orchestrator ever read that field. A round could finish finalization
    with real, named verification failures and still proceed to
    audit/commit as if everything were confirmed, since the
    finalizer's own separate closing report (the one containing this same
    list) only ever reaches norm-engineer's own session, never the
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
    spec: norm-engineer produces a closing report claiming success while
    making zero actual code/config/fluent changes — one real round's own
    closing report was literally {"classification": "success", "message":
    "Round 8 norm specification written..."}, nothing else, not even the
    documented report schema. norm-engineer.md now instructs writing
    state/norm_specs/round_{N}.md *last*, after implementation, for
    exactly this reason (a polished-looking spec written first was the
    thing the model kept mistaking for "done") — but that's a prompt-level
    instruction, not a technical guarantee, so this check still exists as
    the backstop regardless of whether the round even got as far as writing
    a spec. Checked here mechanically via git status against
    NORM_ENGINEER_CODE_PATHS — deliberately NOT the full
    NORM_ROUND_TRACKED_PATHS list, because norm-architect writes
    tests/norm_checks/round_{N}/ *before* norm-engineer ever runs, so that
    directory is already dirty by the time this check executes; using the
    full list here would let a norm-engineer that touched nothing at all
    slip past, since the architect's own pre-existing tests would already
    satisfy a bare "is anything dirty" check. state/norm_specs is
    deliberately not on either list, so a spec-only round — or a round
    that wrote nothing at all — leaves nothing there to see either way —
    never by trusting the model's own self-reported classification, which
    doesn't reliably match the real schema anyway.

    Same known blind spot as everywhere else this exact path list is used
    for a "did the engineer do something" check: state/fluents.json can
    be dirtied by ordinary harvest physics (an agent dying) independent of
    any engineer action, so a round that coincides with a death and
    changes nothing else would slip past this. Accepted deliberately, by
    the same standing decision already made for stage_norm_implementation()
    — not re-litigated here."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--"] + NORM_ENGINEER_CODE_PATHS,
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
    """Rolls back everything this round's norm-architect/norm-engineer
    touched — `errors` states the actual reason (a compile/syntax
    failure, a protected-path violation, an institution.json drift
    mismatch, a process failure/timeout, or unresolved auditor findings
    after repairs run out), printed and logged verbatim rather than a
    generic header."""
    print(f"\nRound {round_number}: discarding this round's norm changes —", file=sys.stderr)
    print("continuing with the previous round's mechanics unchanged. Reason(s):", file=sys.stderr)
    for error in errors:
        print(f"  {error}", file=sys.stderr)

    # Durable, unlike stderr (gitignored slurm-*.err) — the reason for a
    # discard must survive in git history.
    log_call(
        call="norm_round_discarded",
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
        p for p in NORM_ROUND_TRACKED_PATHS
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
        ["git", "clean", "-fd", "--"] + NORM_ROUND_TRACKED_PATHS,
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
    """Stages (git add only, never commits) this round's norm pipeline
    tracked paths; the actual `git commit` happens in commit_round()
    below, which combines this with the round's own artifacts into a
    single commit. Staging happens here regardless of model behavior —
    neither norm-architect nor norm-engineer is reliable about committing
    its own work."""
    subprocess.run(["git", "add"] + NORM_ROUND_TRACKED_PATHS, cwd=ROOT, check=True)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()

    if not staged:
        print(f"Round {round_number}: no changes in the norm pipeline's tracked paths — nothing to commit.")
        log_call(
            call="norm_round_no_changes",
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
# norm-auditor no longer has its own process-retry budget here (2026-09-23)
# — since it stopped running through opencode (see call_norm_auditor_agent()
# in engine/llm_agents.py for why), its own bounded retry loop
# (MAX_AUDITOR_ATTEMPTS, in that same module) already lives inside the
# plain completion call itself, the same place call_fisher_agent's/
# call_critique_agent's retry loops already live — there's no separate
# subprocess/session layer above it to retry any more.
# norm-architect no longer has its own process-retry budget here (2026-09-22)
# — since it stopped running through opencode (see call_norm_architect_agent()
# in engine/llm_agents.py for why), its own bounded retry loop
# (MAX_ARCHITECT_ATTEMPTS, in that same module) already lives inside the
# plain completion call itself, the same place call_fisher_agent's/
# call_critique_agent's retry loops already live — there's no separate
# subprocess/session layer above it to retry any more.
# Same idea again, for norm-engineer's own process. run_norm_engineer()
# returning False now covers three cases: a crash, a timeout, or a session
# that ended abnormally mid-task despite exiting 0 (see
# extract_last_step_reason()). Analyzing a real 12-round run (back when
# this agent also did its own design reasoning, before the norm-architect
# split) found the third case alone accounted for roughly half of all
# invocations — treating any of these as an unretried hard failure (as a
# bare run_norm_engineer() call would) discarded close to half of all
# rounds before real work ever had a chance to happen, regardless of
# whether the eventual code would have been fine. Raised from 2 to 5
# (2026-09-14) after a real round hit the identical "session ended
# abnormally (last step reason: 'tool-calls')" signature on both of its 2
# allowed attempts and was discarded despite the actual code issue never
# having had a chance to be attempted — the failure looks
# session-level/transient, not a deterministic code problem, so a wider
# budget is worth the added worst-case wall time.
MAX_ENGINEER_PROCESS_ATTEMPTS = 5
# A small pause between process-retry attempts — matches the existing
# CALL_DELAY_S convention in engine/llm_agents.py for fisher/critique call
# retries, but kept as its own env var since an opencode subprocess call is
# far heavier than one litellm completion; reusing LLM_CALL_DELAY_S would
# couple two unrelated costs. Shared by both the architect's and the
# engineer's own retry loop below — the same class of pause for the same
# class of failure.
NORM_ENGINEER_RETRY_DELAY_S = float(os.environ.get("NORM_ENGINEER_RETRY_DELAY_S", "5"))


def run_norm_architect_with_retry(round_number):
    """Thin pass-through to run_norm_architect() — kept as its own function
    (rather than inlining it at the call site in implement_and_evaluate_norm())
    purely so that function's own call shape didn't need to change across
    the 2026-09-22 rewrite. Its own retry budget (MAX_ARCHITECT_ATTEMPTS)
    now lives inside call_norm_architect_agent() in engine/llm_agents.py,
    the same place call_fisher_agent's/call_critique_agent's retry loops
    already live — there's no separate opencode subprocess/session layer
    above it to retry any more (see that function's own docstring for why:
    DeepSeek-R1 on Ollama doesn't support tool calling, so norm-architect
    stopped running through opencode entirely)."""
    return run_norm_architect(round_number)


def run_norm_engineer_with_retry(round_number, extra_message=None):
    """Retries run_norm_engineer() itself, up to
    MAX_ENGINEER_PROCESS_ATTEMPTS times, on a process-level failure —
    this is not a finding about the code, so it must not be confused with
    or consume a MAX_NORM_REPAIR_ATTEMPTS repair attempt. Returns
    True/False — same success contract as run_norm_engineer() itself.

    Attempts are paired (1&2, 3&4, 5&6, ...), by request (2026-09-18):
    the second attempt of a pair continues the first's own opencode
    session (--session <id>) instead of starting fresh, so it doesn't
    have to re-read every file the first attempt already read before
    failing; the pair after that always starts fresh again, never
    threading a session past 2 consecutive attempts. This is a narrow,
    bounded reintroduction of the session-continuation idea tried
    unbounded on 2026-09-15 and reverted on 2026-09-17 after a real round
    showed a session that keeps growing across many consecutive calls can
    eventually become too large for the model to even respond to at all,
    burning the whole retry budget on calls that could never succeed.
    Capping continuation to a single pair means the largest a session can
    ever get here is 2 attempts' worth of history, then it's discarded —
    the specific failure mode that made unbounded continuation dangerous
    can't reproduce at that scale."""
    session_id = None
    for attempt in range(1, MAX_ENGINEER_PROCESS_ATTEMPTS + 1):
        success, session_id = run_norm_engineer(
            round_number, extra_message=extra_message, session_id=session_id
        )
        if success:
            return True
        print(f"Round {round_number}: norm-engineer's own process failed, timed out, or was "
              f"truncated mid-task (attempt {attempt}/{MAX_ENGINEER_PROCESS_ATTEMPTS}) — "
              f"retrying the process itself, not spending a repair attempt on it.")
        if attempt < MAX_ENGINEER_PROCESS_ATTEMPTS:
            time.sleep(NORM_ENGINEER_RETRY_DELAY_S)
        # Odd attempt (1, 3, 5, ...): keep session_id, so the very next
        # (even) attempt continues it, completing the pair. Even attempt
        # (2, 4, 6, ...): the pair is now complete — reset so the next
        # attempt starts a brand-new session rather than extending the
        # chain further.
        if attempt % 2 == 0:
            session_id = None
    return False


def norm_implementation_failing_tests_errors(round_number):
    """Self-Correction Gate: runs norm-architect's pre-written suite for
    this round and returns a stack-trace-bearing error on failure. Pure
    Python, no LLM call — feeds the EXISTING MAX_NORM_REPAIR_ATTEMPTS loop
    (via the same compile_errors list every other check already populates)
    rather than a new parallel loop, so a failing test gets fed straight
    back to norm-engineer as a repair message exactly like a compile
    error would.

    Returns [] if the round's test directory doesn't exist — that's
    norm-architect's own failure, already caught upstream by
    run_norm_architect()'s own check, not this function's job to
    re-report."""
    tests_dir = ROOT / "tests" / "norm_checks" / f"round_{round_number}"
    if not tests_dir.is_dir():
        return []
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(tests_dir), "-q"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    if result.returncode == 0:
        return []
    detail = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
    return [
        f"tests/norm_checks/round_{round_number}/ (norm-architect's pre-written suite) is "
        f"still failing:\n{detail}"
    ]


def implement_and_evaluate_norm(round_number, winning_proposal):
    """The per-round pipeline: design (norm-architect, writes failing
    tests + a requirements checklist) -> implement (norm-engineer, against
    that checklist and those tests) -> compile/runtime/self-correction
    checks (with a bounded repair retry) -> independent audit ->
    repair-or-stage. The main loop exists because a compile error, a
    failing pre-written test, or an auditor NEEDS_REPAIR finding can all
    send norm-engineer back for another attempt, sharing one
    MAX_NORM_REPAIR_ATTEMPTS budget. Returns True iff norm-engineer's
    changes were staged (ready for commit_round()'s own single per-round
    commit); False means either a discard already happened, or the round
    was COMPLIANT but made no changes to stage.

    Every call to any of the three agents starts a brand-new opencode
    session — no `--session` continuation across a process retry, a
    compile-error repair, or an auditor NEEDS_REPAIR repair. Session
    continuation was tried here (2026-09-15) and reverted the same month:
    a real round's session grew across ~15 continued calls over ~6 hours
    until it became too large for the model to even begin responding to
    within opencode's own internal provider-header timeout, exhausting the
    entire process-retry budget on calls that could never have succeeded.
    A fresh session every call costs some redundant re-reading of files a
    prior attempt already read, but that cost is bounded and known, unlike
    unbounded context growth."""
    architect_ok, norm_plan = run_norm_architect_with_retry(round_number)
    if not architect_ok:
        discard_norm_implementation(
            round_number,
            ["norm-architect failed to produce a structurally valid plan — see "
             "ops/logs/norm_architect.jsonl and ops/logs/model_calls.jsonl"],
        )
        return False

    success = run_norm_engineer_with_retry(
        round_number, extra_message=render_engineer_kickoff(norm_plan, round_number),
    )
    if not success:
        discard_norm_implementation(
            round_number,
            [f"norm-engineer's process failed, timed out, or was truncated on every attempt "
             f"(after {MAX_ENGINEER_PROCESS_ATTEMPTS} tries) — see ops/logs/model_calls.jsonl"],
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
            # Self-Correction Gate: norm-architect's pre-written suite must
            # actually pass before an LLM-driven audit is even attempted —
            # cheaper and more specific feedback than a full norm-auditor
            # round-trip for a failure this mechanical check already found.
            compile_errors += norm_implementation_failing_tests_errors(round_number)
        if not compile_errors:
            runtime_error = norm_implementation_runtime_errors()
            if runtime_error:
                compile_errors = [runtime_error]
        if compile_errors:
            if attempt > MAX_NORM_REPAIR_ATTEMPTS:
                discard_norm_implementation(round_number, compile_errors)
                return False
            print(f"\nRound {round_number}: norm-engineer's changes have compile/validation "
                  f"errors — sending back for repair (attempt {attempt}/{MAX_NORM_REPAIR_ATTEMPTS}), "
                  f"instead of discarding on the first occurrence.")
            repair_message = (
                f"Round {round_number}'s implementation has compile/validation errors that must "
                f"be fixed before it can even be audited:\n\n{chr(10).join(compile_errors)}\n\n"
                "Fix exactly these errors, then re-run your own verification step "
                "(python3 -m py_compile on every file you touched, plus pytest tests/regression/ "
                f"and tests/norm_checks/round_{round_number}/) yourself before finishing — don't "
                "rely on this message alone to catch the next issue. Don't change anything else "
                "about your implementation beyond what's needed to fix these specific errors. "
                "End your response with the fenced ```json report block your instructions "
                "describe."
            )
            success = run_norm_engineer_with_retry(round_number, extra_message=repair_message)
            if not success:
                discard_norm_implementation(
                    round_number,
                    [f"norm-engineer's repair run failed, timed out, or was truncated on every "
                     f"attempt (after {MAX_ENGINEER_PROCESS_ATTEMPTS} tries) — see "
                     f"ops/logs/model_calls.jsonl"],
                )
                return False
            continue

        # No outer retry loop here any more (2026-09-23) — norm-auditor's
        # own process-level retry budget (MAX_AUDITOR_ATTEMPTS) now lives
        # inside call_norm_auditor_agent() itself (engine/llm_agents.py),
        # the same place call_fisher_agent's/call_critique_agent's retry
        # loops already live, since it's a plain completion call now, not
        # an opencode subprocess this function drove its own retries around.
        audit = run_norm_auditor(round_number)
        if audit is None:
            discard_norm_implementation(
                round_number,
                ["norm-auditor failed to produce a usable verdict — see "
                 "ops/logs/norm_auditor.jsonl and ops/logs/model_calls.jsonl"],
            )
            return False

        if audit["result"] == "COMPLIANT":
            record_institution_changes(round_number)
            return stage_norm_implementation(round_number)

        # The auditor's own free-text report is handed back verbatim as
        # the repair prompt — no structured verdict list to re-parse.
        if attempt > MAX_NORM_REPAIR_ATTEMPTS:
            discard_norm_implementation(
                round_number,
                [f"norm-auditor returned NEEDS_REPAIR after {MAX_NORM_REPAIR_ATTEMPTS} repair "
                 f"attempt(s). Auditor's final report:\n\n{audit['text']}"],
            )
            return False

        print(f"\nRound {round_number}: norm-auditor returned NEEDS_REPAIR — sending back to "
              f"norm-engineer (repair attempt {attempt}/{MAX_NORM_REPAIR_ATTEMPTS}).")
        repair_message = (
            f"Round {round_number}'s auditor found problems — read its full report below "
            "carefully and fix exactly what it identifies. If it's a code/implementation "
            "problem (including an under-enforced requirement — a weaker mechanism than the "
            "norm's own text demands), fix the implementation. If it's a genuine gap in the "
            f"specification (an ambiguity the auditor's own tests exposed), redo that "
            f"requirement's clarification in state/norm_specs/round_{round_number}.md (ask a "
            "sharper question than last time), then adjust the implementation for whatever the "
            "resolution changes. Follow your standing instructions for handling a repair "
            "re-invocation. End your response with the fenced ```json report block your "
            "instructions describe.\n\n"
            f"--- Auditor's report ---\n{audit['text']}\n--- end of report ---"
        )
        success = run_norm_engineer_with_retry(round_number, extra_message=repair_message)
        if not success:
            discard_norm_implementation(
                round_number,
                [f"norm-engineer's repair run failed, timed out, or was truncated on every "
                 f"attempt (after {MAX_ENGINEER_PROCESS_ATTEMPTS} tries) — see "
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
    # round — orchestrator-owned, never a norm-engineer edit target
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

    Kept as a separate `git add` from NORM_ROUND_TRACKED_PATHS'S own
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
        # Distinct from norm_round_discarded/norm_round_no_changes
        # so a plot can read a clean, mutually-exclusive per-round signal.
        log_call(
            call="norm_round_committed",
            agent_id=None, round=round_number, action=None, model=None,
            duration_s=None, returncode=None, prompt=None,
            raw_response=None, parsed_response=None, commit_hash=commit_hash, error=None,
        )
    else:
        print(f"Round {round_number}: committed round artifacts as {commit_hash} "
              f"(logs, norm.txt, runtime state, plots).")


def reload_project_modules():
    """Python caches imported modules for the life of the process — without
    this, a norm-engineer edit to roles/*.py, actions/handlers/*.py,
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
    it's off-limits to norm-engineer by construction (nothing in
    it is on any tracked-path list), so nothing there can change mid-run."""
    for prefix in ("roles", "actions", "objects"):
        for name in sorted(n for n in list(sys.modules) if n == prefix or n.startswith(prefix + ".")):
            importlib.reload(sys.modules[name])


def clean_pycache_dirs():
    """Removes every __pycache__ directory in the repo. Not needed for
    correctness — reload_project_modules() above already forces a fresh
    re-import every round regardless of what's on disk, and
    PYTHONDONTWRITEBYTECODE=1 (set in hpc_ollama_entrypoint.sh) stops new
    ones from being written in the first place — this is defense-in-depth
    for whatever's already on disk (a resumed checkout, a local dev run
    without that env var set) and for one real, practical reason: the
    norm-architect/norm-engineer/norm-auditor/norm-finalizer agents' own `read`/
    `glob` tools kept surfacing these (harmless bytecode, not source) as
    if they were real files to inspect, needing five depth-specific
    permission.read denies apiece just to route around them. Actually
    removing them is more direct than only denying reads to them."""
    for cache_dir in ROOT.rglob("__pycache__"):
        try:
            shutil.rmtree(cache_dir)
        except OSError:
            pass  # best-effort; never worth failing a round over


def refresh_codegraph_index():
    """Full clean rebuild of the CodeGraph index (`unlock` -> `rm -rf
    .codegraph` -> `init`, never `sync` — see hpc_ollama_entrypoint.sh's
    own job-start block for the same sequence and why `sync` specifically
    is avoided, a real hang on Aoraki root-caused to that one command).
    Re-added here per-round (2026-09-16, by request) as insurance against
    a stale index — `opencode.jsonc`'s `codegraph serve --mcp` is a
    *local* MCP server, spawned fresh as a child of each `opencode run`
    call, not a long-lived process spanning rounds; only the on-disk
    `.codegraph/codegraph.db` persists between them, and whether a freshly
    started server re-validates it against the real filesystem before
    answering queries first was never actually confirmed. A real round
    already showed a *different* kind of stale-artifact contamination
    (leftover __pycache__ naming a discarded rule after its own .py file
    was gone — see clean_pycache_dirs()); this closes the analogous risk
    for CodeGraph's own index rather than waiting to find out the hard
    way it has the same one.

    Same graceful-degradation shape as every other optional refresh in
    this file: no `codegraph` binary, a timeout, or any other failure
    means the norm pipeline agents fall back to plain Read/Grep for that
    round — never worth blocking or crashing a round over."""
    if shutil.which("codegraph") is None:
        return
    try:
        subprocess.run(
            ["codegraph", "--no-color", "unlock", "."],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        shutil.rmtree(ROOT / ".codegraph", ignore_errors=True)
        result = subprocess.run(
            ["codegraph", "--no-color", "init", "."],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            print("CodeGraph index refresh failed — continuing without it "
                  "(the norm pipeline agents fall back to plain Read/Grep):",
                  file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            shutil.rmtree(ROOT / ".codegraph", ignore_errors=True)
    except subprocess.TimeoutExpired:
        print("CodeGraph index refresh didn't finish within its timeout — "
              "continuing without it, same as any other failure here.", file=sys.stderr)
        shutil.rmtree(ROOT / ".codegraph", ignore_errors=True)
    except OSError as exc:
        print(f"CodeGraph index refresh failed to even start ({exc}) — "
              "continuing without it.", file=sys.stderr)


def run_cycle(round_number):
    """Runs every state/schedule.json action gated on for this round, in
    file order. Skips actions already recorded for this round (resuming
    after a crash mid-round). Returns False if the lake collapsed."""
    print(f"\n=== Round {round_number} ===")
    clean_pycache_dirs()
    refresh_codegraph_index()
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
            print(f"\nRound {round_number}: norm changes already committed for this round, skipping.")
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
    """Never let a run's state/code changes or norm pipeline commits land
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
