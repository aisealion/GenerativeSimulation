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

try:
    # matplotlib isn't part of the minimal HPC venv hpc_ollama_entrypoint.sh
    # builds (litellm/pydantic/python-dotenv only) unless that script has
    # been updated to install it too — monitoring is observability, not
    # core simulation logic, so its absence degrades to a no-op the same
    # way the optional memory layer already does, rather than taking the
    # whole round loop down over a missing plotting dependency.
    from engine.monitoring import update_plots
except ImportError as exc:
    print(f"  [monitoring disabled: {exc}]")

    def update_plots(state):
        pass

ROOT = Path(__file__).resolve().parent.parent
COLLAPSE_THRESHOLD_KG = 0
DEFAULT_MAX_ROUNDS = 100
NORM_IMPLEMENTER_TRACKED_PATHS = [
    # state/runtime.json is deliberately never on this list — it's
    # simulation-owned (the implementer must never write it; see PHASE 1
    # of both norm-implementer.md files) and it's what commit_round_artifacts()
    # further down commits separately, every round, unconditionally — kept
    # off this list so a discard's `git clean -fd` (scoped to exactly this
    # list) can never touch it.
    # norms/ replaced mechanisms/ + phases/ here (2026-08-27) — the
    # norm-implementer's per-norm enforcement logic now lives entirely in
    # norms/*.py plugins; mechanisms/ and phases/ are no longer on its
    # permission.edit allowlist at all (see .opencode/agent/
    # norm-implementer.md), so a norm round no longer touches either.
    "norms",
    "prompts",
    # Implementer-authored unit tests for its own mechanism/phase changes
    # (added 2026-08-26) — distinct from tests/regression/, which stays a
    # human-owned fixed suite the implementer must never edit. Tracked here
    # so a new test file actually gets committed, and so a syntax error in
    # one is caught by the same compile gate as everything else, rather
    # than silently sitting broken until the next round tries to run it.
    "tests/norm_checks",
    "schedule.json",
    "state/config.json",
    "state/fluents.json",
    "state/fluents_schema.md",
    # engine/simulate.py itself is now editable by the norm-implementer
    # (was previously denied — see CLAUDE.md for why that changed and the
    # residual risk). It has to be listed here for two reasons: so
    # commit_norm_implementation()'s `git add` actually picks up edits to
    # it (before this, an edit landed on disk but never got committed by
    # the deterministic path — it had to be committed by hand instead),
    # and so norm_implementation_compile_errors() below includes it in the
    # pre-commit syntax check, since it derives its file list from this
    # same list.
    "engine/simulate.py",
]

HOLDS_AT_RE = re.compile(r"holdsAt\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)")


def load_state(round_number):
    return {
        "config": json.loads((ROOT / "state" / "config.json").read_text()),
        "fluents": json.loads((ROOT / "state" / "fluents.json").read_text()),
        "runtime": json.loads((ROOT / "state" / "runtime.json").read_text()),
        "agents": json.loads((ROOT / "state" / "agents.json").read_text()),
        "round_number": round_number,
    }


def load_schedule():
    return json.loads((ROOT / "schedule.json").read_text())


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
        raise ValueError(f"unsupported schedule.json gate condition: {condition!r}")

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


def write_memory_episodes(phase, state, record, round_number):
    """The memory layer (Graphiti/Neo4j) is optional, local-only infra for
    now — it's never deployed on Aoraki, and a dev machine may not have it
    running either. Never let its absence, or any failure in it, block a
    round: skip fast if NEO4J_URI isn't even set, and never let an error
    here propagate past a warning."""
    if not os.environ.get("NEO4J_URI"):
        return
    try:
        from engine.memory.write import write_episode

        for spec in phase.memory_writes(state, record):
            write_episode(round_num=round_number, **spec)
    except Exception as exc:
        print(f"  [memory write skipped: {exc}]")


def write_fact_memory_events(state, round_number):
    """Mirrors write_memory_episodes() above, but for fluent-sourced events
    (mechanisms.roles.set_fact()/end_fact() calls carrying narration) rather
    than a phase's own memory_writes() hook. Called once per round, after
    every phase for that round has finished — not per-phase like
    write_memory_episodes() — because fact_memory_events() finds facts by
    initiated_round/terminated_round == round_number, and a fact set by an
    early phase would still look "new" to a later phase's own call this
    same round, double-writing it to memory."""
    if not os.environ.get("NEO4J_URI"):
        return
    try:
        from engine.memory.write import write_episode
        from mechanisms.roles import fact_memory_events

        for spec in fact_memory_events(state["fluents"], round_number):
            write_episode(round_num=round_number, **spec)
    except Exception as exc:
        print(f"  [memory write skipped: {exc}]")


def parse_opencode_jsonl(stdout):
    """Parses `opencode run --format json`'s JSONL event stream: counts
    completed tool_use events (per-round tool-call telemetry) and keeps
    the last text event's content as the model's final response (where the
    Step 6 report lives). Documented opencode behavior, not empirically
    verified against the installed 1.18.14 build — no model credentials
    available to exercise a real run while writing this. Degrades
    gracefully on any parse failure (falls back to a zero count and the
    raw stdout) rather than raising, so a schema mismatch here costs
    telemetry, not the round itself."""
    tool_calls = 0
    final_text = None
    try:
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event.get("type") == "tool_use":
                tool_calls += 1
            elif event.get("type") == "text":
                text = event.get("part", {}).get("text")
                if text:
                    final_text = text
    except (json.JSONDecodeError, AttributeError):
        return 0, stdout
    return tool_calls, final_text or stdout


def extract_norm_implementer_report(text):
    """Pulls the trailing fenced ```json block (Step 6 of both
    norm-implementer specs) out of its final response. Takes the last
    match, in case the report text quotes other JSON earlier; returns
    None on no-match or a malformed block rather than raising — a report
    parse failure shouldn't be able to break a round any more than a
    missing tool-call count can."""
    matches = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def run_norm_implementer(round_number):
    """Returns True on a completed (returncode 0) run, False on anything
    else — a timeout, a crash, a non-zero exit. Used to raise
    unconditionally: a failed norm-implementer run ended the whole
    simulate.py process, taking every remaining round down with it over
    one bad round. That was always a real risk (any opencode crash or a
    genuinely slow round hitting the 3600s ceiling below), and re-enabling
    CodeGraph's daemon mode (see CODEGRAPH_NO_DAEMON's removal in
    hpc_ollama_entrypoint.sh) makes a hang more likely to actually happen,
    not just theoretically possible — daemon/sync is the exact mechanism
    already root-caused as hanging on Aoraki once before (see CLAUDE.md).
    False here now means "treat this round like a discarded/failed norm
    implementation" (same as a compile error) — the round's own mechanics
    stay whatever they were before this attempt, and a similar norm gets
    another chance to be implemented later, instead of losing the rest of
    the run to one bad round."""
    print("\n--- invoking norm-implementer ---")
    message = (
        "norm.txt has been updated for this round. Read it and implement "
        "accordingly, following your standing instructions."
    )
    cmd = ["opencode", "run", "--agent", "norm-implementer", "--format", "json"]
    model = os.environ.get("OPENCODE_MODEL")
    if model:
        cmd += ["--model", model]
    cmd.append(message)

    # Raised alongside the norm-implementer's own `steps: 500` (was 60,
    # .opencode/agent/norm-implementer.md) — a genuinely thorough run using
    # that much bigger budget could now take longer than the old 900s
    # (15min) ceiling, which would just cut it off here instead, making the
    # step increase pointless. Local models only cost wall time, not money,
    # so a generous ceiling is fine; still bounded, not unbounded — bounded
    # is what actually matters now that a timeout here is caught below
    # instead of crashing the whole run.
    start = time.monotonic()
    try:
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired:
        duration_s = time.monotonic() - start
        print(f"Round {round_number}: norm-implementer didn't finish within 3600s — "
              f"treating this round's norm implementation as failed, not crashing the run.",
              file=sys.stderr)
        log_call(
            call="norm_implementer", agent_id=None, round=round_number, phase=None,
            model=model, duration_s=round(duration_s, 3), returncode=None,
            prompt=message, raw_response=None, parsed_response=None,
            tool_call_count=None, report=None, error="timeout after 3600s",
        )
        return False

    duration_s = time.monotonic() - start
    tool_call_count, final_text = parse_opencode_jsonl(result.stdout)
    report = extract_norm_implementer_report(final_text)

    log_call(
        call="norm_implementer",
        agent_id=None,
        round=round_number,
        phase=None,
        model=model,
        duration_s=round(duration_s, 3),
        returncode=result.returncode,
        prompt=message,
        raw_response=result.stdout,
        parsed_response=None,
        tool_call_count=tool_call_count,
        report=report,
        error=None if result.returncode == 0 else result.stderr.strip(),
    )

    print(final_text)
    if result.returncode != 0:
        print(f"Round {round_number}: norm-implementer exited with code {result.returncode} — "
              f"treating this round's norm implementation as failed, not crashing the run.",
              file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return False
    return True


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
        (r for r in runtime["rounds"] if r["round"] == round_number and r["phase"] == "vote"), None
    )
    if vote_record is None:
        return None
    propose_record = next(
        (r for r in runtime["rounds"] if r["round"] == round_number and r["phase"] == "propose"), None
    )
    return propose_record["proposals"][vote_record["winning_proposer"]]


def norm_implementation_compile_errors():
    # Syntax-check every touched .py file and validate every touched .json
    # file, before anything gets committed — a broken edit here blocks
    # every future round too, since reload_project_modules() re-imports
    # from disk at the start of each one. Also confirms every norm "type"
    # referenced in state/config.json actually has a matching registered
    # class (checked in a fresh subprocess so a stale in-process NORM_TYPES
    # snapshot can't hide a type this round just added) — a config can be
    # syntactically valid JSON and still reference nothing real.
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
    # Actually run HarvestPhase against fabricated state (no real LLM
    # calls, monkeypatched fisher response) — once using whatever
    # config.json currently activates, then once per registered norm type
    # standalone with generic params, so a type that compiles and passes
    # the checks above but was never wired into config (dead code) still
    # gets exercised instead of sitting silently broken. Run in a fresh
    # subprocess: this runs mid-round, before reload_project_modules()
    # would next pick up whatever this round just changed on disk.
    script = (
        "import sys, json\n"
        "sys.path.insert(0, '.')\n"
        "import phases.harvest as harvest_module\n"
        "from engine.norms.registry import NORM_TYPES\n"
        "from engine.norms.context import HarvestContext\n"
        "\n"
        "def _fake_call_fisher_agent(agent_id, round_number, phase_name, **fields):\n"
        "    return {'effort': 0.5, 'reasoning': 'orchestrator smoke test'}\n"
        "harvest_module.call_fisher_agent = _fake_call_fisher_agent\n"
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
        "    'round_number': 1,\n"
        "}\n"
        "harvest_module.PHASE.run(state)\n"
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
        return f"Harvest runtime check (active config + every registered norm type):\n{detail}"
    return None


def discard_norm_implementation(round_number, errors):
    """Roll back everything the norm-implementer touched this round — a
    partially-broken change (a working mechanisms/effort.py alongside a
    broken phases/harvest.py, say) is exactly as unsafe to leave on disk as
    a fully broken one, since reload_project_modules() re-imports all of it
    regardless. Safe to do unconditionally here: commit_norm_implementation()
    hasn't run yet, so nothing from this round has been committed —
    `git checkout --` reverts modified tracked files back to HEAD, `git
    clean -fd` removes any newly-created untracked files/dirs (a new phase
    file for a new_phase norm, say) that checkout alone wouldn't touch."""
    print(f"\nRound {round_number}: norm-implementer's changes don't compile — discarding", file=sys.stderr)
    print("them and continuing with the previous round's mechanics unchanged:", file=sys.stderr)
    for error in errors:
        print(f"  {error}", file=sys.stderr)

    # Durable, not just stderr: stderr only lives in slurm-*.err, which is
    # gitignored and never gets pushed — the exact reason for a discard was
    # unrecoverable after the fact the first time this happened for real.
    # logs/model_calls.jsonl is tracked, so this survives.
    log_call(
        call="norm_implementer_discarded",
        agent_id=None,
        round=round_number,
        phase=None,
        model=None,
        duration_s=None,
        returncode=None,
        prompt=None,
        raw_response=None,
        parsed_response=None,
        error="\n\n".join(errors),
    )

    subprocess.run(
        ["git", "checkout", "--"] + NORM_IMPLEMENTER_TRACKED_PATHS,
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "clean", "-fd", "--"] + NORM_IMPLEMENTER_TRACKED_PATHS,
        cwd=ROOT, check=True, capture_output=True, text=True,
    )


def commit_norm_implementation(round_number, winning_proposal):
    """The norm-implementer is unreliable about running its own git commit —
    observed across real runs, it consistently skips it regardless of
    instructions. Don't depend on model compliance for something this
    mechanical: commit deterministically here instead, scoped to exactly the
    paths the agent is allowed to touch (never state/runtime.json)."""
    subprocess.run(["git", "add"] + NORM_IMPLEMENTER_TRACKED_PATHS, cwd=ROOT, check=True)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()

    if not staged:
        print(f"Round {round_number}: norm-implementer made no changes in the tracked paths — nothing to commit.")
        log_call(
            call="norm_implementer_no_changes",
            agent_id=None, round=round_number, phase=None, model=None,
            duration_s=None, returncode=None, prompt=None,
            raw_response=None, parsed_response=None, error=None,
        )
        return None

    message = f"Round {round_number} norm: {winning_proposal['policy']}\n\n{winning_proposal['operationalization']}"
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True, capture_output=True, text=True)
    commit_hash = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    print(f"Committed round {round_number} as {commit_hash}: {winning_proposal['policy'][:72]}")
    # Distinct from norm_implementer_discarded — the only other log_call()
    # this function's caller can reach — so plot 6 (engine/monitoring.py)
    # gets a clean, mutually-exclusive per-round commit/discard/no-op
    # signal without inferring anything from git log.
    log_call(
        call="norm_implementer_committed",
        agent_id=None, round=round_number, phase=None, model=None,
        duration_s=None, returncode=None, prompt=None,
        raw_response=None, parsed_response=None, commit_hash=commit_hash, error=None,
    )
    return commit_hash


ROUND_ARTIFACT_PATHS = [
    "logs",
    "norm.txt",
    "plots",
    "state/runtime.json",
    "state/agents.json",
]


def commit_round_artifacts(round_number):
    """Commit the round's own produced data — logs, norm.txt, runtime
    state, plots — every round, unconditionally, regardless of whether
    this round's norm itself committed, was a no-op, or got discarded.
    Without this, the only thing making it into git history is whatever a
    human happens to sweep up in a manual commit — real logs/model_calls.jsonl
    and norm.txt content have been lost this way before (a crash or an
    interrupted run before the next manual commit). Every round of
    forensic archaeology this session has depended on
    logs/model_calls.jsonl actually existing in git — this is what makes
    that reliable going forward instead of incidental.

    Deliberately NOT folded into NORM_IMPLEMENTER_TRACKED_PATHS/
    commit_norm_implementation() above, on purpose, not an oversight:
    that list is scoped to what the norm-implementer is allowed to touch
    and — critically — what discard_norm_implementation() is allowed to
    `git clean -fd` on a discard. logs/ and norm.txt are exactly the
    forensic record of *why* a round got discarded; if they were on that
    list they'd be at risk of being wiped by the very discard they explain.
    state/runtime.json is simulation-owned and already explicitly
    off-limits to the implementer for the same reason it's not tracked
    there either (see NORM_IMPLEMENTER_TRACKED_PATHS's own docstring
    note) — this is the orchestrator committing its own output, not
    granting the implementer any new reach.

    A real cost worth naming, not hiding: state/runtime.json grows every
    round and gets committed every round here, so a long many-round run
    accumulates real repo history size this way. Traded deliberately in
    favor of never losing round data to an interrupted run again — this
    project's own history has already hit that failure mode more than
    once."""
    existing = [p for p in ROUND_ARTIFACT_PATHS if (ROOT / p).exists()]
    if not existing:
        return
    subprocess.run(["git", "add"] + existing, cwd=ROOT, check=True)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    if not staged:
        return
    subprocess.run(
        ["git", "commit", "-m", f"Round {round_number} artifacts: logs, norm.txt, runtime state, plots"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    print(f"Round {round_number}: committed round artifacts (logs, norm.txt, runtime state, plots).")


def refresh_knowledge_graph(round_number):
    """Keep the Understand-Anything semantic graph current after a round
    actually changes code — without this, it's frozen at whatever it looked
    like when hpc_ollama_entrypoint.sh built it before round 1, and gets
    more wrong every round after that (norm-implementer's own PHASE 2
    staleness check would just keep reporting it as unusable — no point
    building it at all if nothing ever refreshes it).

    Deliberately NOT done via the plugin's own `autoUpdate`/hook mechanism
    (SessionStart / PostToolUse in understand-anything-plugin/hooks/
    hooks.json): that mechanism assumes the agent whose session it's
    watching is the one running `git commit` and can act on the "you must
    update now" instruction it injects. Neither holds here — this project's
    commit_norm_implementation() above commits via a plain subprocess, not
    through any agent's own tool calls, so the PostToolUse hook would never
    fire at all; and norm-implementer's own SessionStart hook would fire
    every round but inject an instruction it's structurally unable to
    follow (permission.task: deny blocks the subagent dispatch a graph
    update needs), just burning step budget on every single round for
    nothing. So this runs the refresh directly, as its own `build`-agent
    `opencode run` call — same reasoning as the initial build in
    hpc_ollama_entrypoint.sh (norm-implementer can't dispatch subagents;
    opencode's default `build` agent can) — right after a round's commit
    actually lands, from the orchestrator, not from inside any agent
    session's own hooks.

    Gated by the same BUILD_KNOWLEDGE_GRAPH=1 opt-in as the initial build:
    if that was never set, no graph exists yet, and /understand's own
    Phase 0 decision logic would treat a missing graph as "run a full
    analysis" rather than a genuinely incremental one — silently far more
    expensive than intended. Checking the env var here (rather than just
    checking whether a graph file exists) keeps this symmetric with
    whatever hpc_ollama_entrypoint.sh actually did at job start.

    No `--full`: /understand's own decision table runs an incremental
    update (only files changed since the graph's stored commit hash) when
    a graph already exists — much cheaper than the initial full build, so
    a shorter timeout than that one's 1800s is appropriate. Failure here is
    never fatal to the round; same graceful-degradation shape as
    hpc_ollama_entrypoint.sh's own codegraph/understand-anything blocks —
    a stale-but-present graph is what PHASE 2's own staleness check is
    already built to handle, so there's no reason to let this block the
    round or the rest of the run.
    """
    if os.environ.get("BUILD_KNOWLEDGE_GRAPH") != "1":
        return
    print(f"\n--- refreshing Understand-Anything knowledge graph (round {round_number}) ---")
    # --command names the skill directly instead of hoping a prose message
    # gets inferred as one. --format json so raw_response actually captures
    # the session (opencode's default format writes to stderr, not stdout).
    # --auto because the build agent's external_directory permission
    # defaults to "ask", and the plugin's own checkout lives outside the
    # project directory — headless, no one to answer, so it silently
    # auto-denies the pnpm build step without this (see CLAUDE.md).
    cmd = ["opencode", "run", "--agent", "build", "--format", "json", "--auto"]
    model = os.environ.get("OPENCODE_MODEL")
    if model:
        cmd += ["--model", model]
    # Trailing message required: --command alone loads the skill into
    # context and then just stops there without executing a single phase.
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
            call="knowledge_graph_refresh", agent_id=None, round=round_number, phase=None,
            model=model, duration_s=600.0, returncode=None, prompt=" ".join(cmd),
            raw_response=None, parsed_response=None, error="timeout",
        )
        return

    duration_s = time.monotonic() - start
    tool_call_count, final_text = parse_opencode_jsonl(result.stdout)
    # Exit code alone isn't trustworthy — the same silent-no-op failure
    # above returned 0. Verify the graph's own stored commit hash actually
    # caught up to HEAD rather than trusting the process's own report.
    error = None if result.returncode == 0 else result.stderr.strip()
    if error is None and not knowledge_graph_matches_head():
        error = "opencode exited 0 but the graph's stored commit hash didn't advance to HEAD — likely a silent no-op"
    if error:
        print(f"Round {round_number}: knowledge graph refresh failed ({error}) — continuing "
              f"with the graph as it was.", file=sys.stderr)
    log_call(
        call="knowledge_graph_refresh", agent_id=None, round=round_number, phase=None,
        model=model, duration_s=round(duration_s, 3), returncode=result.returncode,
        prompt=" ".join(cmd), raw_response=result.stdout, tool_call_count=tool_call_count,
        parsed_response=final_text, error=error,
    )


def knowledge_graph_matches_head():
    """True iff a knowledge graph exists and its stored gitCommitHash
    (meta.json, written by /understand's own Phase 7) equals the current
    HEAD — the only reliable way to tell a refresh actually did something,
    since a failed/no-op opencode invocation has been observed to still
    exit 0 (see refresh_knowledge_graph())."""
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
    this, a norm-implementer edit to mechanisms/*.py, norms/*.py, or
    phases/*.py on disk never actually takes effect within a single
    continuous simulate.py run, only the very first round's version of
    that code ever executes. Modules not yet imported (a brand new plugin
    or phase file) don't need reloading — the plain import a few lines
    down already gets them fresh.

    norms/ needs more than the mechanisms/phases pattern: engine.norms.
    registry's NORM_TYPES is a module-level statement
    (`NORM_TYPES = _discover_norm_types()`), computed exactly once at
    first import, not recomputed lazily — reloading norms/*.py alone
    doesn't make it re-scan. Confirmed missing this caused a real problem:
    on one actual run, two rounds each added a genuinely new norms/*.py
    plugin file mid-run, and neither ever became usable within that same
    continuous process even after config referenced it — this is exactly
    the failure mode the registry's own auto-discovery design was
    supposed to make impossible. Order matters throughout: reload
    dependencies before their dependents, so each already-imported
    module's own `from x import y` name bindings get refreshed to the
    newly reloaded objects, not left pointing at stale ones —
    mechanisms/norms first (no project-internal deps of their own),
    then engine.norms.registry (rebinds its own NORM_TYPES against the
    freshly reloaded norms/*.py classes), then engine.norms.engine
    (rebinds its own `from engine.norms.registry import load_norms` to
    the fresh function registry.py's reload just created), then phases
    (rebinds phases/harvest.py's own `from engine.norms.engine import
    NormEngine` the same way, and mechanisms.x imports same as before)."""
    for prefix in ("mechanisms", "norms"):
        for name in sorted(n for n in list(sys.modules) if n == prefix or n.startswith(prefix + ".")):
            importlib.reload(sys.modules[name])
    for module_name in ("engine.norms.registry", "engine.norms.engine"):
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
    for name in sorted(n for n in list(sys.modules) if n == "phases" or n.startswith("phases.")):
        importlib.reload(sys.modules[name])


def run_cycle(round_number):
    """Run every schedule.json phase gated on for this round, in file order.
    Skips phases already recorded for this round (resuming after a crash
    mid-round) instead of re-running or skipping past them. Returns False
    if the lake collapsed this round (stop the simulation)."""
    print(f"\n=== Round {round_number} ===")
    reload_project_modules()
    state = load_state(round_number)
    schedule = load_schedule()
    already_ran = {r["phase"] for r in state["runtime"]["rounds"] if r["round"] == round_number}

    for phase_name, gate in schedule.items():
        if phase_name in already_ran:
            print(f"--- {phase_name}: already recorded for round {round_number}, resuming past it ---")
            continue
        if not evaluate_gate(gate, state["fluents"], round_number):
            print(f"--- {phase_name}: gated off this round ---")
            continue

        print(f"\n--- Round {round_number}: {phase_name} ---")
        phase_module = importlib.import_module(f"phases.{phase_name}")
        record = phase_module.PHASE.run(state)
        save_runtime(state)
        save_fluents(state)
        print(json.dumps(record, indent=2))
        write_memory_episodes(phase_module.PHASE, state, record, round_number)

        if state["runtime"]["stock_kg"] <= COLLAPSE_THRESHOLD_KG:
            print(
                f"\nLake has collapsed at round {round_number} "
                f"(stock_kg={state['runtime']['stock_kg']}). Stopping."
            )
            # This early return skips update_plots()/commit_round_artifacts()
            # below — without calling it here too, the single most
            # narratively important round of the whole run (the one that
            # actually ends it) would be exactly the one round whose data
            # never makes it into git.
            commit_round_artifacts(round_number)
            return False

    write_fact_memory_events(state, round_number)

    winning_proposal = state.get("adopted_norm") or find_adopted_norm(state["runtime"], round_number)
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
            if not run_norm_implementer(round_number):
                discard_norm_implementation(
                    round_number, ["norm-implementer run itself failed or timed out — see logs/model_calls.jsonl"]
                )
            else:
                compile_errors = norm_implementation_compile_errors()
                if not compile_errors:
                    runtime_error = norm_implementation_runtime_errors()
                    if runtime_error:
                        compile_errors = [runtime_error]
                if compile_errors:
                    discard_norm_implementation(round_number, compile_errors)
                else:
                    commit_hash = commit_norm_implementation(round_number, winning_proposal)
                    if commit_hash:
                        refresh_knowledge_graph(round_number)

    update_plots(state)
    commit_round_artifacts(round_number)

    return True


def round_is_complete(runtime, fluents, schedule, round_number):
    recorded = {r["phase"] for r in runtime["rounds"] if r["round"] == round_number}
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
    schedule = load_schedule()

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
