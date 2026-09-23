"""Asks the fisher who proposed the round's adopted rule what an ambiguous
or incomplete requirement actually means — or puts a specific
contradiction/gap in the norm's own text to them directly, a real critique
rather than a neutral clarifying question (see NORM_ARCHITECT_SYSTEM_PROMPT
in engine/llm_agents.py, "Critique, not just clarify"). Never used to
change norm.txt, and never answered by norm-architect itself — only the
proposer's own call_fisher_agent() response counts. Logged through the
same log_call()/ops/logs/model_calls.jsonl path every other fisher call
uses (call="fisher", action="clarify"), so no separate log file is needed
to review these after the fact.

ask_norm_proposer() is called directly (a plain function import) from
engine.simulate's norm-architect flow — no subprocess/CLI involved there
any more (2026-09-22: norm-architect stopped running through opencode
after DeepSeek-R1 turned out not to support tool calling on Ollama; a
plain completion call has no bash tool to shell out with anyway). The CLI
below is kept only for manual/ad-hoc use from a terminal.

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
        (r for r in runtime["rounds"] if r["round"] == round_number and r["action"] == "vote"), None
    )
    if vote_record is None:
        return None, None
    propose_record = next(
        (r for r in runtime["rounds"] if r["round"] == round_number and r["action"] == "propose"), None
    )
    proposer_id = vote_record["winning_proposer"]
    return proposer_id, propose_record["proposals"][proposer_id]


def ask_norm_proposer(round_number, question):
    """Returns the proposer's {"answer": ..., "reasoning": ...} dict, or
    raises RuntimeError if this round has no adopted proposal (shouldn't
    happen — the norm pipeline only ever runs for a round that has one)."""
    runtime = json.loads((ROOT / "state" / "runtime.json").read_text())
    proposer_id, proposal = _winning_proposer_and_proposal(runtime, round_number)
    if proposer_id is None:
        raise RuntimeError(f"no adopted proposal found for round {round_number}")

    return call_fisher_agent(
        proposer_id,
        round_number,
        "clarify",
        policy=proposal["policy"],
        operationalization=proposal["operationalization"],
        question=question,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Ask the fisher who proposed this round's adopted rule to clarify one specific point."
    )
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--question", required=True)
    args = parser.parse_args()

    try:
        response = ask_norm_proposer(args.round, args.question)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(response))


if __name__ == "__main__":
    main()
