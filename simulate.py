#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import phases.harvest as harvest
import phases.propose as propose
import phases.vote as vote
from call_log import log_call

ROOT = Path(__file__).resolve().parent
COLLAPSE_THRESHOLD_KG = 0
DEFAULT_MAX_ROUNDS = 50


def load_state(round_number):
    return {
        "config": json.loads((ROOT / "state" / "config.json").read_text()),
        "fluents": json.loads((ROOT / "state" / "fluents.json").read_text()),
        "runtime": json.loads((ROOT / "state" / "runtime.json").read_text()),
        "agents": json.loads((ROOT / "state" / "agents.json").read_text()),
        "round_number": round_number,
    }


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
    """Harvest, then propose + vote + implement — every round renegotiates.
    Returns False if the lake collapsed this round (stop the simulation)."""
    print(f"\n=== Round {round_number}: harvest ===")
    state = load_state(round_number)
    harvest_record = harvest.run(state)
    save_runtime(state)
    save_fluents(state)
    print(json.dumps(harvest_record, indent=2))

    if harvest_record["stock_kg_after_regrowth"] <= COLLAPSE_THRESHOLD_KG:
        print(
            f"\nLake has collapsed at round {round_number} "
            f"(stock_kg_after_regrowth={harvest_record['stock_kg_after_regrowth']}). Stopping."
        )
        return False

    print(f"\n=== Round {round_number}: propose + vote ===")
    propose_record = propose.run(state)
    save_runtime(state)
    print(json.dumps(propose_record, indent=2))

    vote_record, winning_proposal = vote.run(state)
    save_runtime(state)
    print(json.dumps(vote_record, indent=2))

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
