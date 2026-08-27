#!/bin/bash
# Runs *inside* the apptainer container's environment — this is the command
# run_simulation.slurm hands to `apptainer run` after it starts the ollama
# server and exports OLLAMA_HOST, not something you run directly.
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

# A plain `bash script.sh` invocation never sources ~/.bashrc (that only
# happens for interactive shells) — so even if opencode was installed in a
# previous run and its PATH line added there, this shell doesn't see it.
# Set it explicitly rather than depending on a startup file that doesn't
# apply here; harmless if the directory doesn't exist yet.
export PATH="$HOME/.opencode/bin:$PATH"

# codegraph runs first, before anything Ollama-related below — deliberately
# moved here (was previously after the model pulls/creates). Every
# standalone reproduction of codegraph init/sync has succeeded (login node,
# an actual GPU compute node via srun, interactive and non-interactive
# apptainer invocations, exact env vars matched) — the one thing none of
# those reproductions had was the Ollama server + two ~dozens-of-GB model
# pulls/creates running concurrently, which this script's original
# ordering did. Root cause still unconfirmed either way, but there's no
# real dependency forcing codegraph to run after that section, so moving
# it first removes that variable for free regardless of whether it was
# ever the actual cause.
#
# codegraph: same problem opencode above had (installed but not on PATH
# here) would apply, plus it was never installed here at all yet — the
# earlier `npm install -g` route used to set this up doesn't apply on a
# node that likely has no Node.js. This installer is Node-free (a
# self-contained bundle) and puts a symlink in ~/.local/bin by default.
export PATH="$HOME/.local/bin:$PATH"
if ! command -v codegraph >/dev/null 2>&1; then
  echo "codegraph not found (checked \$HOME/.local/bin) — installing there"
  curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh
fi

# --no-color: codegraph's default output uses cursor-control ANSI codes
# meant for a live TTY (spinners etc.) — dumped into a SLURM log file
# instead of a real terminal, that just accumulates as garbled control
# sequences, not a hang by itself, but makes the log unreadable and makes
# an actual hang harder to see. Telemetry off for the same "don't ship
# anything unnecessary off this cluster" reasoning as everywhere else here.
#
# CodeGraph's own docs say init/sync are purely local — no API calls, no
# credentials, nothing beyond this optional telemetry ping — and every
# hypothesis tried here (restricted network, NFS+SQLite locking, a daemon/
# file-watcher, non-interactive/no-TTY invocation) has been individually
# ruled out by direct reproduction. CODEGRAPH_NO_DAEMON kept set regardless
# — cheap, and rules out the daemon path even though it didn't turn out to
# be the cause on its own.
export CODEGRAPH_TELEMETRY=0
export CODEGRAPH_NO_DAEMON=1

# .codegraph/ is a local, per-checkout index — never committed to git (see
# .gitignore) — so it doesn't exist yet on a fresh clone of this repo, which
# is exactly the situation on a cluster you haven't run this on before.
# Without it, opencode.jsonc's codegraph MCP server finds no index and
# exposes no tools at all, and the norm-implementer silently falls back to
# plain Read/Grep instead of codegraph_explore — no error, just quietly
# worse exploration.
#
# Always a full clean init, never `codegraph sync` — this is the actual
# root cause finally caught red-handed on a real run: with .codegraph/
# already present (from an earlier manual build), the old `[ -d .codegraph ]`
# check picked `sync`, and *that* is what hung at 120s — "even running
# first, before any Ollama/model work" per its own error message, which
# ruled out every other theory being tried at the time. Every standalone
# reproduction that succeeded (login node, an actual GPU compute node,
# interactive and non-interactive) was `init` after an explicit `rm -rf
# .codegraph` — `sync` itself was never actually tested standalone, because
# every manual test deliberately started from a clean slate. codegraph's own
# docs describe `sync` as normally triggered *by the file watcher*, not run
# directly — it may simply not be designed to be invoked as a one-shot CLI
# command the way this script was using it. This repo is 19 files and a
# full `init` takes low single digits of seconds even under real load, so
# there's no real cost to always doing a full rebuild instead of trying to
# use the (apparently broken, in this context) incremental path.
#
# unlock first: codegraph has its own documented failure mode of "a stale
# lock file blocking indexing" (codegraph unlock exists specifically for
# this) — a real risk here given how many times this job has been killed
# and resubmitted while debugging this. Safe to run even if nothing is
# actually locked.
codegraph --no-color unlock . 2>&1 || true
rm -rf .codegraph

echo "Building a fresh CodeGraph index..."
# Wrapped in a hard timeout: if it's still stuck for some other reason, fail
# loudly and say so, rather than silently eating the rest of the job's wall
# time. codegraph init on this repo's ~19 files took low single-digit
# seconds in every direct reproduction so far (worst case observed: 36s,
# under real load on an active GPU compute node), so 120s is a generous
# margin, not a tight one.
if ! timeout 120 codegraph --no-color init .; then
  echo "codegraph init didn't finish within 120s, even running first, before" >&2
  echo "any Ollama/model work, and even as a full init rather than sync (the" >&2
  echo "specific thing that was hanging before — see the comment above). If" >&2
  echo "this is still failing, the cause is something not yet isolated by any" >&2
  echo "reproduction tried so far. Continuing without a CodeGraph index: the" >&2
  echo "norm-implementer will fall back to plain Read/Grep, which still works," >&2
  echo "just with worse exploration." >&2
  rm -rf .codegraph
fi

echo "Inside the Ollama container environment, OLLAMA_HOST=${OLLAMA_HOST:-<not set>}"
if [ -z "${OLLAMA_HOST:-}" ]; then
  echo "OLLAMA_HOST wasn't set inside the container — ollama-env.sh's behavior" >&2
  echo "may differ from what this script assumes. Check 'cat \$(command -v" >&2
  echo "ollama-env.sh)' and the container's own runscript." >&2
  exit 1
fi

echo "Waiting for the ollama server at ${OLLAMA_HOST} to accept connections..."
ready=false
for i in $(seq 1 30); do
  if curl -sf -m 5 "http://${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 2
done
if [ "$ready" != true ]; then
  echo "ollama server at ${OLLAMA_HOST} never became ready after 60s — this is" >&2
  echo "what was hanging before. Check logs/ollama-related output above for why" >&2
  echo "the server itself didn't start (GPU driver issue, OOM, etc.)." >&2
  exit 1
fi

# Two different models for the two agent types: the fisher (many small,
# fast decisions per round — 10 agents x 3 phases) runs on gpt-oss:20b;
# the norm-implementer (one heavier code-editing call per round, via
# opencode) runs on gpt-oss:120b. Both must already be present — same
# never-auto-pull policy as before, just checked twice now.
for MODEL_TAG in "gpt-oss:20b" "gpt-oss:120b"; do
  echo "Checking ${MODEL_TAG} is present under OLLAMA_MODELS=${OLLAMA_MODELS:-<unset>} (not downloading it)..."
  if ! ollama list | grep -q "$MODEL_TAG"; then
    echo "${MODEL_TAG} not found via 'ollama list'. You said this is already" >&2
    echo "downloaded manually — check OLLAMA_MODELS points at the right directory," >&2
    echo "or run 'ollama list' yourself in this same environment to see what tag" >&2
    echo "it's actually registered under." >&2
    exit 1
  fi
  echo "Found ${MODEL_TAG}."
done

# Ollama caps every model's context window at 4096 tokens by default,
# regardless of what the model itself supports (gpt-oss:120b advertises
# 128K, gpt-oss:20b also well beyond 4096) — confirmed elsewhere to fail
# *silently* when exceeded: a response with only reasoning tokens and no
# actual answer, not a clear error. That's very likely what the earlier
# "no JSON object found in agent response: ''" retries were actually
# hitting, not a random transient hiccup — this repo's prompts grow every
# round (history window, codegraph_explore output, and now a 10-agent
# proposals list for the vote phase). Create an extended-context variant
# of each model rather than relying on the 4096 default. Override
# OLLAMA_NUM_CTX if 32768 isn't enough for either.
OLLAMA_NUM_CTX="${OLLAMA_NUM_CTX:-32768}"
OLLAMA_20B_CTX_MODEL_ID="gpt-oss-20b-${OLLAMA_NUM_CTX}ctx"
OLLAMA_120B_CTX_MODEL_ID="gpt-oss-120b-${OLLAMA_NUM_CTX}ctx"

echo "Creating extended-context variant ${OLLAMA_20B_CTX_MODEL_ID} (num_ctx=${OLLAMA_NUM_CTX}) from gpt-oss:20b..."
printf 'FROM gpt-oss:20b\nPARAMETER num_ctx %s\n' "$OLLAMA_NUM_CTX" > /tmp/fishery-20b.Modelfile
ollama create "$OLLAMA_20B_CTX_MODEL_ID" -f /tmp/fishery-20b.Modelfile

echo "Creating extended-context variant ${OLLAMA_120B_CTX_MODEL_ID} (num_ctx=${OLLAMA_NUM_CTX}) from gpt-oss:120b..."
printf 'FROM gpt-oss:120b\nPARAMETER num_ctx %s\n' "$OLLAMA_NUM_CTX" > /tmp/fishery-120b.Modelfile
ollama create "$OLLAMA_120B_CTX_MODEL_ID" -f /tmp/fishery-120b.Modelfile

# Point opencode's "ollama" provider at THIS job's actual (randomly-assigned)
# port instead of the committed opencode.jsonc's fixed 127.0.0.1:11434
# default. .opencode/opencode.json is gitignored — opencode merges it in
# automatically as an extra project-local config layer, nothing tracked
# gets touched. Only the 120b variant needs to be listed here — the fisher
# no longer goes through opencode at all (see below), so opencode never
# needs to know about the 20b model.
mkdir -p .opencode
cat > .opencode/opencode.json << EOF
{
  "\$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Local Ollama (Aoraki)",
      "options": {
        "baseURL": "http://${OLLAMA_HOST}/v1",
        "apiKey": "ollama"
      },
      "models": {
        "gpt-oss:120b": { "name": "GPT-OSS 120B (Aoraki Ollama)" },
        "${OLLAMA_120B_CTX_MODEL_ID}": { "name": "GPT-OSS 120B, ${OLLAMA_NUM_CTX}-token context (Aoraki Ollama)" }
      }
    }
  }
}
EOF

if ! command -v opencode >/dev/null 2>&1; then
  echo "opencode not found (checked \$HOME/.opencode/bin) — installing there"
  curl -fsSL https://opencode.ai/install | bash
fi

# The fisher agent no longer goes through opencode — llm_agents.py calls
# litellm directly. litellm's response types use pydantic forward
# references (TypedDicts backed by typing_extensions) that need a matching
# resolution stack, or construction fails with "Message is not fully
# defined ... call Message.model_rebuild()".
#
# History, in order ruled out on 2026-08-19: NOT system-vs-user
# site-packages shadowing (reproduced identically inside a from-scratch
# isolated venv). NOT litellm/pydantic/pydantic-core version mismatch
# (pinning all three to the exact versions verified working locally still
# failed identically). Root-caused by diffing `pip freeze` on both sides:
# pydantic's own direct dependencies (annotated-types, typing-extensions,
# typing-inspection) were still unpinned and resolved to newer releases on
# Aoraki than what was actually verified end-to-end here; anyio/jiter
# (openai/httpx's stack) differed too. This is the full pinned set that
# fixed it — see pyproject.toml for the same list with more detail.
FISHERY_VENV="$SLURM_SUBMIT_DIR/.venv-fishery"
if [ ! -d "$FISHERY_VENV" ]; then
  echo "Creating isolated venv at ${FISHERY_VENV} for litellm/pydantic..."
  python3 -m venv "$FISHERY_VENV"
fi
# Some minimal container images strip ensurepip, which leaves a venv
# created without pip inside it — silently, `python3 -m venv` still exits
# 0 in that case. Check explicitly rather than letting the next line fail
# with a confusing "No such file or directory" on $FISHERY_VENV/bin/pip.
if [ ! -x "$FISHERY_VENV/bin/pip" ]; then
  echo "python3 -m venv created ${FISHERY_VENV} but it has no pip inside —" >&2
  echo "this container's Python likely lacks ensurepip. Bootstrap it by hand:" >&2
  echo "  curl -sS https://bootstrap.pypa.io/get-pip.py | ${FISHERY_VENV}/bin/python3" >&2
  echo "then resubmit." >&2
  exit 1
fi
"$FISHERY_VENV/bin/pip" install --quiet --upgrade pip \
  litellm==1.97.0 pydantic==2.13.4 pydantic-core==2.46.4 \
  annotated-types==0.7.0 typing-extensions==4.15.0 typing-inspection==0.4.2 \
  anyio==4.14.0 jiter==0.15.0 python-dotenv matplotlib
# matplotlib (added for engine/monitoring.py's live plots, 2026-08-26) is
# unpinned, unlike everything above it — it doesn't have the fragile
# cross-package resolution issue that pinning exists to work around here,
# so it doesn't need the same treatment. engine/simulate.py imports
# engine.monitoring defensively (try/except ImportError) specifically so
# forgetting this line degrades to "no live plots" rather than crashing
# every round at import time — but the whole point of this feature is
# watching a long unattended HPC run's progress, so it shouldn't actually
# be left out.

# Reproduce the exact failure point from the 2026-08-19 incident
# (ModelResponse() construction) right here, so a real break fails loudly
# before round 1 rather than three silent retries into it. Crucially, this
# must go through engine/llm_agents.py (like engine/simulate.py actually
# does), NOT a bare `import litellm` — llm_agents.py applies a workaround
# at import time for a genuine litellm bug on Python 3.10 (Message's
# pydantic schema has a forward ref that never resolves there; see
# _patch_litellm_message_rebuild() in engine/llm_agents.py). A bare
# `from litellm.types.utils import ModelResponse` check bypasses that
# workaround entirely and fails even when the real engine/simulate.py run
# would succeed — cost real time chasing exactly that false alarm on
# 2026-08-19/20 before catching it.
if ! "$FISHERY_VENV/bin/python3" -c "
import sys
sys.path.insert(0, '$SLURM_SUBMIT_DIR')
import engine.llm_agents
from litellm.types.utils import ModelResponse
ModelResponse()
"; then
  echo "Still broken even going through engine/llm_agents.py's own workaround." >&2
  echo "Full dependency tree for a direct diff:" >&2
  "$FISHERY_VENV/bin/pip" freeze >&2
  exit 1
fi
echo "litellm/pydantic/pydantic-core verified working inside ${FISHERY_VENV}."

mkdir -p logs
# OPENCODE_MODEL still drives the norm-implementer (still an opencode agent,
# gets the bigger 120b model — one heavier code-editing call per round).
# FISHER_MODEL drives the fisher's direct litellm calls (gets the smaller,
# faster 20b model — up to agent_count x 3 calls per round). Different
# models now, not just different env vars pointing at the same one.
#
# Both models live on the same GPU, and gpt-oss:120b alone can already use
# most of an H100's 80GB VRAM at this context length — Ollama likely can't
# keep both loaded simultaneously, so expect it to swap models in and out
# between the fisher's calls and the once-per-round norm-implementer call
# (at most one swap each way per round, since all fisher calls happen
# before the norm-implementer's). That's added per-round latency, not a
# correctness issue, but factor it into --time and MAX_ROUNDS sizing.
export OPENCODE_MODEL="ollama/${OLLAMA_120B_CTX_MODEL_ID}"
export FISHER_MODEL="ollama/${OLLAMA_20B_CTX_MODEL_ID}"

# Understand-Anything: a semantic ("what is this for") complement to
# CodeGraph's structural ("what calls what") index — see CLAUDE.md's
# "Understand-Anything" section. Opt-in, off by default: unlike codegraph
# init (a few seconds, zero LLM calls, pure parsing), building this graph
# means opencode dispatching a real subagent per batch of files across the
# whole repo — genuine LLM time on the same GPU the fisher/norm-implementer
# calls already share, not something every ordinary run should pay for.
# Set BUILD_KNOWLEDGE_GRAPH=1 to opt in.
#
# Skills are installed for opencode the same way codegraph is above
# (install-if-missing, from the tool's own official installer) — but unlike
# codegraph, installing the skill files here doesn't require Node.js on this
# node: it's just `git clone` + symlinks (verified by reading install.sh
# directly before ever running it — see CLAUDE.md). Node/pnpm would only be
# needed by the graph-*building* pipeline's own Node scripts, which run
# inside the opencode subprocess below, in whatever environment opencode
# itself provides — untested on Aoraki specifically; if that's missing
# there, expect this whole block to fail and fall through to the
# graceful-skip path, same as any other failure here.
if [ "${BUILD_KNOWLEDGE_GRAPH:-0}" = "1" ]; then
  if ! find "$HOME/.agents/skills" -maxdepth 1 -name 'understand*' -print -quit 2>/dev/null | grep -q .; then
    echo "Understand-Anything skills not found — installing for opencode"
    curl -fsSL https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.sh | bash -s opencode
  fi

  # .ua/ is gitignored and machine-local (see .gitignore) — same reasoning
  # as .codegraph/ above: nothing to reuse or sync from a previous run on
  # this same checkout, so always build fresh rather than trying an
  # incremental update whose correctness here is unverified.
  rm -rf .ua .understand-anything

  echo "Building the Understand-Anything knowledge graph (BUILD_KNOWLEDGE_GRAPH=1)..."
  # --agent build: norm-implementer deliberately has permission.task=deny
  # (a hardening choice, not a technical limit — see CLAUDE.md) so it can
  # never dispatch the subagents this pipeline needs. opencode's default
  # "build" agent has no such restriction (permission "*": allow), which is
  # what actually makes this scriptable via the same `opencode run`
  # subprocess pattern engine/simulate.py already uses for the
  # norm-implementer, not a fundamentally different mechanism.
  # --model reuses OPENCODE_MODEL (the 120b variant) rather than pulling or
  # configuring a third model just for this.
  # Generous timeout, not a tight one: unverified how long a real run takes
  # here — if it's still stuck, fail this step loudly and continue without
  # a graph (norm-implementer's PHASE 2 already treats a missing graph as
  # non-blocking — falls back to CodeGraph + direct reading), exactly like
  # codegraph's own graceful-degradation pattern above, rather than eating
  # the rest of this job's wall time.
  if ! timeout 1800 opencode run --agent build --model "$OPENCODE_MODEL" \
    "Run /understand --full --no-auto-update on this project." \
    > logs/understand-anything-build.log 2>&1; then
    echo "Understand-Anything build didn't finish within 1800s or failed —" >&2
    echo "see logs/understand-anything-build.log. Continuing without a" >&2
    echo "knowledge graph: the norm-implementer will fall back to CodeGraph" >&2
    echo "+ direct reading, which still works, just without the semantic view." >&2
    rm -rf .ua .understand-anything
  fi
fi

# Run through the venv's interpreter, not the container's bare python3 —
# that's the whole point of building it above. engine/simulate.py itself
# and everything it imports besides engine/llm_agents.py and
# engine/monitoring.py (engine/call_log, mechanisms/*, phases/*) is
# stdlib-only, so this venv (litellm/pydantic/python-dotenv/matplotlib,
# no --system-site-packages) has everything the run needs; the opencode
# subprocess call for the norm-implementer is an external binary,
# unaffected by which Python interpreter launched it.
# Run as a module (-m engine.simulate), not a script path, so `engine`
# resolves as a package relative to $SLURM_SUBMIT_DIR (the repo root and
# cwd here) — a plain `python3 engine/simulate.py` would put engine/ itself
# on sys.path instead and break every `from engine.x import y` inside it.
"$FISHERY_VENV/bin/python3" -m engine.simulate --max-rounds "${MAX_ROUNDS:-100}"
