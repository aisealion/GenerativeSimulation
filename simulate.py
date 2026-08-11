#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

import phases.harvest as harvest
import phases.propose as propose
import phases.vote as vote

ROOT = Path(__file__).resolve().parent


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


def run_norm_implementer():
    print("\n--- invoking norm-implementer ---")
    result = subprocess.run(
        [
            "opencode",
            "run",
            "--agent",
            "norm-implementer",
            "norm.txt has been updated for this round. Read it and implement "
            "accordingly, following your standing instructions.",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=900,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError("norm-implementer run failed")


def main():
    print("=== Round 1: harvest ===")
    state = load_state(round_number=1)
    record = harvest.run(state)
    save_runtime(state)
    save_fluents(state)
    print(json.dumps(record, indent=2))

    print("\n=== Round 2: propose + vote ===")
    state = load_state(round_number=2)
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

    run_norm_implementer()

    print("\n=== Round 3: harvest (post-norm) ===")
    state = load_state(round_number=3)
    record = harvest.run(state)
    save_runtime(state)
    save_fluents(state)
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
