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

from call_log import log_call

ROOT = Path(__file__).resolve().parent
COLLAPSE_THRESHOLD_KG = 0
DEFAULT_MAX_ROUNDS = 100
NORM_IMPLEMENTER_TRACKED_PATHS = [
    "mechanisms",
    "phases",
    "prompts",
    "schedule.json",
    "state/config.json",
    "state/fluents.json",
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
        from memory.write import write_episode

        for spec in phase.memory_writes(state, record):
            write_episode(round_num=round_number, **spec)
    except Exception as exc:
        print(f"  [memory write skipped: {exc}]")


def run_norm_implementer(round_number):
    print("\n--- invoking norm-implementer ---")
    message = (
        "norm.txt has been updated for this round. Read it and implement "
        "accordingly, following your standing instructions."
    )
    cmd = ["opencode", "run", "--agent", "norm-implementer"]
    model = os.environ.get("OPENCODE_MODEL")
    if model:
        cmd += ["--model", model]
    cmd.append(message)

    # Raised alongside the norm-implementer's own `steps: 500` (was 60,
    # .opencode/agent/norm-implementer.md) — a genuinely thorough run using
    # that much bigger budget could now take longer than the old 900s
    # (15min) ceiling, which would just cut it off here instead, making the
    # step increase pointless. Local models only cost wall time, not money,
    # so a generous ceiling is fine; still bounded, not unbounded.
    start = time.monotonic()
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=3600)
    duration_s = time.monotonic() - start

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
        error=None if result.returncode == 0 else result.stderr.strip(),
    )

    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError("norm-implementer run failed")


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
    """Syntax-check every .py file the norm-implementer could have touched,
    before anything gets committed. Without this, a broken edit gets
    committed deterministically by commit_norm_implementation() below, and
    then permanently blocks every future round too — reload_project_modules()
    re-imports these files from disk at the start of every single round, so
    a syntax error here doesn't just fail this round, it fails the rest of
    the run and needs manual git surgery to recover from (this happened for
    real: a broken phases/harvest.py got committed and crashed every
    subsequent round with an IndentationError)."""
    errors = []
    for directory in ("mechanisms", "phases"):
        for py_file in sorted((ROOT / directory).rglob("*.py")):
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(py_file)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                errors.append(f"{py_file.relative_to(ROOT)}:\n{result.stderr.strip()}")
    return errors


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
        return None

    message = f"Round {round_number} norm: {winning_proposal['policy']}\n\n{winning_proposal['operationalization']}"
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True, capture_output=True, text=True)
    commit_hash = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    print(f"Committed round {round_number} as {commit_hash}: {winning_proposal['policy'][:72]}")
    return commit_hash


def reload_project_modules():
    """Python caches imported modules for the life of the process — without
    this, a norm-implementer edit to mechanisms/*.py or phases/*.py on disk
    never actually takes effect within a single continuous simulate.py run,
    only the very first round's version of that code ever executes. Reload
    mechanisms before phases so phases' `from mechanisms.x import y`
    statements re-bind to the freshly reloaded functions, not stale ones
    captured at the first import. Modules not yet imported (a brand new
    phase file) don't need reloading — the plain import a few lines down
    already gets them fresh."""
    for prefix in ("mechanisms", "phases"):
        for name in sorted(n for n in list(sys.modules) if n == prefix or n.startswith(prefix + ".")):
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
            return False

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
            run_norm_implementer(round_number)
            compile_errors = norm_implementation_compile_errors()
            if compile_errors:
                discard_norm_implementation(round_number, compile_errors)
            else:
                commit_norm_implementation(round_number, winning_proposal)

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
