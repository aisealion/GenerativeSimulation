#!/usr/bin/env python3
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

    run_norm_implementer(round_number=2)

    print("\n=== Round 3: harvest (post-norm) ===")
    state = load_state(round_number=3)
    record = harvest.run(state)
    save_runtime(state)
    save_fluents(state)
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
