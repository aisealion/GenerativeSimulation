#!/usr/bin/env python3
"""Shows what an opencode-driven norm pipeline agent (norm-engineer or its
norm-finalizer subagent) actually did in a session — every tool call
(codegraph_explore queries, files read, files edited), not just the final
summary text that ops/logs/model_calls.jsonl captures. Our own logging
only sees stdout; this reads opencode's own session store for the real
tool-call trace. Doesn't apply to norm-architect or norm-auditor — as of
2026-09-22/23 both are plain, tool-free litellm completion calls (see
engine/llm_agents.py) with no opencode session to inspect; their own
prompt/response is already fully captured in ops/logs/norm_architect.jsonl
/ norm_auditor.jsonl.

Usage (run from the repo root — this script itself lives under ops/,
alongside run_simulation.slurm/hpc_ollama_entrypoint.sh/logs/plots, kept
out of the repo root so opencode's own read/glob/grep exploration never
wastes a tool call on it; see CLAUDE.md's "ops/ split" entry):
  python3 ops/inspect_session.py              # most recent matching session
  python3 ops/inspect_session.py --list       # list all matching sessions
  python3 ops/inspect_session.py <session_id> # a specific session (any agent)
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

TITLE_MARKERS = ("norm.txt", "implement norm")


def list_sessions():
    result = subprocess.run(
        ["opencode", "session", "list", "--format", "json"], capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def find_norm_pipeline_sessions():
    sessions = list_sessions()
    matches = [s for s in sessions if any(m in s["title"].lower() for m in TITLE_MARKERS)]
    return sorted(matches, key=lambda s: s["created"], reverse=True)


def export_session(session_id):
    # opencode export's stdout can be large enough (100KB+) to hit a pipe
    # buffering issue with subprocess.run(capture_output=True) — redirect
    # to a temp file instead, which doesn't have that problem.
    with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
        with open(tmp.name, "w") as out:
            subprocess.run(["opencode", "export", session_id], stdout=out, stderr=subprocess.PIPE, check=True)
        return json.loads(Path(tmp.name).read_text())


def print_trace(session_id):
    data = export_session(session_id)
    print(f"=== session {session_id} ===\n")
    for i, message in enumerate(data["messages"]):
        role = message.get("info", {}).get("role")
        for part in message.get("parts", []):
            ptype = part.get("type")
            if ptype == "tool":
                tool = part.get("tool")
                inp = part.get("state", {}).get("input", {})
                if tool == "codegraph_codegraph_explore":
                    print(f"[{i:>2}] codegraph_explore  query={inp.get('query')!r}")
                elif tool in ("read", "edit", "write"):
                    print(f"[{i:>2}] {tool:<6}            {inp.get('filePath')}")
                elif tool == "bash":
                    print(f"[{i:>2}] bash              {inp.get('command')}")
                else:
                    print(f"[{i:>2}] {tool}  {json.dumps(inp)[:100]}")
            elif ptype == "text" and role == "assistant":
                text = part.get("text", "").strip()
                if text:
                    print(f"[{i:>2}] ({role} says) {text[:100]}")


def main():
    args = sys.argv[1:]

    if args and args[0] == "--list":
        for s in find_norm_pipeline_sessions():
            print(s["id"], s["title"])
        return

    if args:
        print_trace(args[0])
        return

    matches = find_norm_pipeline_sessions()
    if not matches:
        print("No norm pipeline sessions found yet.")
        return
    print_trace(matches[0]["id"])


if __name__ == "__main__":
    main()
