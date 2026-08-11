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
DEFAULT_MAX_ROUNDS = 50

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

    start = time.monotonic()
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900)
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


def run_cycle(round_number):
    """Run every schedule.json phase gated on for this round, in file order.
    Returns False if the lake collapsed this round (stop the simulation)."""
    print(f"\n=== Round {round_number} ===")
    state = load_state(round_number)
    schedule = load_schedule()

    for phase_name, gate in schedule.items():
        if not evaluate_gate(gate, state["fluents"], round_number):
            print(f"--- {phase_name}: gated off this round ---")
            continue

        print(f"\n--- Round {round_number}: {phase_name} ---")
        phase_module = importlib.import_module(f"phases.{phase_name}")
        record = phase_module.run(state)
        save_runtime(state)
        save_fluents(state)
        print(json.dumps(record, indent=2))

        if state["runtime"]["stock_kg"] <= COLLAPSE_THRESHOLD_KG:
            print(
                f"\nLake has collapsed at round {round_number} "
                f"(stock_kg={state['runtime']['stock_kg']}). Stopping."
            )
            return False

    if "adopted_norm" in state:
        winning_proposal = state["adopted_norm"]
        norm_text = (
            f"Policy: {winning_proposal['policy']}\n\n"
            f"Operationalization: {winning_proposal['operationalization']}\n"
        )
        (ROOT / "norm.txt").write_text(norm_text)
        print(f"\nAdopted norm written to norm.txt:\n{norm_text}")
        run_norm_implementer(round_number)

    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=DEFAULT_MAX_ROUNDS,
        help="Safety backstop: stop after this many total rounds even if the lake hasn't collapsed.",
    )
    args = parser.parse_args()

    runtime = json.loads((ROOT / "state" / "runtime.json").read_text())
    round_number = runtime["round"] + 1

    while round_number <= args.max_rounds:
        if not run_cycle(round_number):
            print(f"\n=== Simulation ended: lake collapse at round {round_number} ===")
            return
        round_number += 1

    print(f"\n=== Simulation ended: reached the {args.max_rounds}-round safety cap without collapse ===")


if __name__ == "__main__":
    main()
