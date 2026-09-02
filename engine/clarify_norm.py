"""CLI the norm-implementer agent invokes (via Bash) during PHASE 1 to ask
the fisher who proposed the round's adopted rule what an ambiguous or
incomplete requirement actually means. Never used to change norm.txt, and
never answered by the norm-implementer itself — only the proposer's own
call_fisher_agent() response counts. Logged through the same
log_call()/logs/model_calls.jsonl path every other fisher call uses
(call="fisher", phase="clarify"), so no separate log file is needed to
review these after the fact.

Usage: python3 -m engine.clarify_norm --round <N> --question "<question>"
Prints the fisher's JSON response ({"answer": ..., "reasoning": ...}) to
stdout.
"""
import argparse
import json
import sys
from pathlib import Path

from engine.llm_agents import call_fisher_agent

ROOT = Path(__file__).resolve().parent.parent


def _winning_proposer_and_proposal(runtime, round_number):
    """Same lookup shape as engine.simulate.find_adopted_norm(), but also
    returns the proposer's agent_id — needed here to know who to ask,
    which find_adopted_norm() itself has no reason to expose."""
    vote_record = next(
        (r for r in runtime["rounds"] if r["round"] == round_number and r["phase"] == "vote"), None
    )
    if vote_record is None:
        return None, None
    propose_record = next(
        (r for r in runtime["rounds"] if r["round"] == round_number and r["phase"] == "propose"), None
    )
    proposer_id = vote_record["winning_proposer"]
    return proposer_id, propose_record["proposals"][proposer_id]


def main():
    parser = argparse.ArgumentParser(
        description="Ask the fisher who proposed this round's adopted rule to clarify one specific point."
    )
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--question", required=True)
    args = parser.parse_args()

    runtime = json.loads((ROOT / "state" / "runtime.json").read_text())
    proposer_id, proposal = _winning_proposer_and_proposal(runtime, args.round)
    if proposer_id is None:
        print(f"error: no adopted proposal found for round {args.round}", file=sys.stderr)
        sys.exit(1)

    response = call_fisher_agent(
        proposer_id,
        args.round,
        "clarify",
        policy=proposal["policy"],
        operationalization=proposal["operationalization"],
        question=args.question,
    )
    print(json.dumps(response))


if __name__ == "__main__":
    main()
