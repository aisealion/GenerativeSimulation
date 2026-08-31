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
# ruled out by direct reproduction. Telemetry off for the same "don't ship
# anything unnecessary off this cluster" reasoning as everywhere else here.
export CODEGRAPH_TELEMETRY=0
#
# CODEGRAPH_NO_DAEMON removed (2026-08-27) — trying CodeGraph's actual
# standard/intended design: opencode.jsonc's `codegraph serve --mcp` runs a
# background file-watcher that keeps the index live on its own, so the
# norm-implementer's codegraph_explore/impact/callers MCP tool calls are
# always current without anyone explicitly re-running init/sync per round
# (that manual per-round refresh — see .opencode/agent/norm-implementer.md
# PHASE 2 — was itself only ever a workaround for not trusting this path).
# Deliberately not the same thing as the original incident: that was
# specifically `codegraph sync` invoked as a one-shot CLI command outside
# the daemon's own control (its docs describe sync as normally
# daemon-triggered, not meant to be run directly) — the daemon *itself* was
# separately tested and cleared by direct reproduction (see above), it was
# only ever left off out of low-cost caution, not because it was the
# confirmed cause. Still, this is a real, not-fully-eliminated risk in the
# specific repeated-across-many-rounds production context that standalone
# reproduction never exercised — engine/simulate.py's run_norm_implementer()
# was hardened the same day to catch a hung/failed opencode invocation and
# discard that round rather than crash the whole multi-round run, so a
# recurrence here costs one round, not the rest of the job. Re-add
# `export CODEGRAPH_NO_DAEMON=1` above to revert to the previous
# manual-refresh-only behavior if this turns out to still be the cause.

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
# FISHER_MODEL drives the fisher's direct litellm calls — stays the local
# Ollama 20b model (up to agent_count x 3 calls per round, so it needs to
# be the fast/local one).
#
# NORM_IMPLEMENTER_MODEL routes the norm-implementer's opencode invocation
# specifically (engine/simulate.py's run_norm_implementer() checks this
# var before falling back to OPENCODE_MODEL) — by request, this is now
# litellm/Kimi-K2.5 over the Otago LiteLLM proxy, not a local Ollama model.
# Deliberately a *separate* var from OPENCODE_MODEL rather than repointing
# OPENCODE_MODEL itself: OPENCODE_MODEL is also what the Understand-Anything
# build-agent calls use (the one-time initial build below, plus
# engine/simulate.py's refresh_knowledge_graph() after any round that
# commits a norm, both gated on BUILD_KNOWLEDGE_GRAPH=1) — those should
# keep using the local 120b model regardless of what the norm-implementer
# itself is routed to, since the user only asked to move the
# norm-implementer.
#
# Practical effect: the norm-implementer's once-per-round call no longer
# competes with the fisher for the same GPU/VRAM at all (only the fisher's
# 20b and, when BUILD_KNOWLEDGE_GRAPH=1, the build agent's 120b share it
# now — and those two don't run concurrently either, so the "Ollama swaps
# models" latency concern this comment used to describe mostly goes away
# for an ordinary run). The new cost is a hard dependency on
# LITELLM_API_KEY and real network egress from this compute node to
# llm.uod.otago.ac.nz for every single round's norm-implementer call —
# both already confirmed working from Aoraki compute nodes during the
# CodeGraph investigation (see CLAUDE.md), so not a new risk, just a new
# per-round dependency that didn't exist when everything ran on local
# Ollama.
export NORM_IMPLEMENTER_MODEL="litellm/Kimi-K2.5"
export OPENCODE_MODEL="ollama/${OLLAMA_120B_CTX_MODEL_ID}"
export FISHER_MODEL="ollama/${OLLAMA_20B_CTX_MODEL_ID}"

if [ -z "${LITELLM_API_KEY:-}" ]; then
  echo "NORM_IMPLEMENTER_MODEL=litellm/Kimi-K2.5 but LITELLM_API_KEY isn't set in" >&2
  echo "this job's environment — every round's norm-implementer call would fail." >&2
  echo "sbatch propagates the submitting shell's environment by default, so" >&2
  echo "export LITELLM_API_KEY before running sbatch, or pass it explicitly:" >&2
  echo "  sbatch --export=ALL,LITELLM_API_KEY=... run_simulation.slurm" >&2
  exit 1
fi

# Neo4j / Graphiti memory layer (engine/memory/) — previously "local-only
# infra, never deployed on Aoraki" (see CLAUDE.md), by design: nothing here
# ever set NEO4J_URI, and write_memory_episodes()/render_relevant_memories()
# both check `if not os.environ.get("NEO4J_URI")` before touching anything
# memory-related, so its absence was always a silent, correct no-op rather
# than a crash. Opt-in now via ENABLE_NEO4J_MEMORY=1 (off by default — same
# reasoning as BUILD_KNOWLEDGE_GRAPH below: real new failure surface and
# job-startup latency, not something every ordinary run should pay for
# unverified).
#
# 2026-08-28: switched from a nested-Apptainer-instance approach to a
# portable binary run as a plain background process instead — a real job
# confirmed the `apptainer` binary simply isn't reachable inside
# ollama_shellenv.sif at all, so nested container orchestration was a dead
# end on this specific image, not something worth retrying. This mirrors
# how Ollama itself already runs inside this same container: a plain
# server process, not a nested container. Real new dependency this
# approach introduces: Java 17+ must be reachable inside the container
# (Neo4j 5.x's requirement) — unconfirmed as of this writing, checked at
# runtime below and skipped gracefully if missing, same degradation
# philosophy as everywhere else in this file.
if [ "${ENABLE_NEO4J_MEMORY:-0}" = "1" ]; then
  if ! command -v java >/dev/null 2>&1; then
    echo "ENABLE_NEO4J_MEMORY=1 but no 'java' binary is reachable inside this" >&2
    echo "container — Neo4j 5.x needs Java 17+. Continuing without the memory" >&2
    echo "layer (NEO4J_URI stays unset)." >&2
  else
    # Persistent storage, same convention as OLLAMA_MODELS above: the
    # extracted Neo4j installation and its data both survive across job
    # resubmissions, so only the very first run pays for the download, and
    # the graph accumulates across runs rather than starting empty every
    # time. The whole distribution (not just data/logs) lives under
    # NEO4J_HOME so no neo4j.conf edits are needed to redirect directories
    # — bin/neo4j already reads everything relative to NEO4J_HOME.
    NEO4J_STORE_DIR="/projects/sciences/computing/cranefield_lab/magha601/neo4j"
    NEO4J_HOME="$NEO4J_STORE_DIR/neo4j-home"
    NEO4J_PASSWORD_FILE="$NEO4J_STORE_DIR/password"
    NEO4J_INIT_MARKER="$NEO4J_STORE_DIR/.initialized"
    mkdir -p "$NEO4J_STORE_DIR"

    # Version chosen to match the 5.26.x line already exercised locally
    # against this same engine/memory/client.py (Graphiti's bolt driver) —
    # not the newest release, a known-compatible one.
    NEO4J_TARBALL_URL="https://dist.neo4j.org/neo4j-community-5.26.0-unix.tar.gz"
    if [ ! -x "$NEO4J_HOME/bin/neo4j" ]; then
      echo "Neo4j not found at $NEO4J_HOME — downloading $NEO4J_TARBALL_URL"
      echo "(one-time; needs egress to dist.neo4j.org from this compute node,"
      echo "unconfirmed as of this writing — a different dependency from both"
      echo "llm.uod.otago.ac.nz and Docker Hub, see CLAUDE.md)."
      NEO4J_DOWNLOAD_DIR="$NEO4J_STORE_DIR/download"
      mkdir -p "$NEO4J_DOWNLOAD_DIR"
      if curl -fsSL "$NEO4J_TARBALL_URL" -o "$NEO4J_DOWNLOAD_DIR/neo4j.tar.gz"; then
        rm -rf "$NEO4J_HOME"
        mkdir -p "$NEO4J_HOME"
        # --strip-components=1: the tarball's own top-level directory
        # (neo4j-community-5.26.0) becomes NEO4J_HOME's contents directly.
        tar -xzf "$NEO4J_DOWNLOAD_DIR/neo4j.tar.gz" -C "$NEO4J_HOME" --strip-components=1 || rm -rf "$NEO4J_HOME"
      else
        echo "Failed to download Neo4j from $NEO4J_TARBALL_URL — continuing" >&2
        echo "without the memory layer (NEO4J_URI stays unset)." >&2
      fi
      rm -rf "$NEO4J_DOWNLOAD_DIR"
    fi

    if [ ! -x "$NEO4J_HOME/bin/neo4j" ]; then
      echo "Neo4j still not found at $NEO4J_HOME/bin/neo4j after the download" >&2
      echo "attempt — continuing without the memory layer (NEO4J_URI stays unset)." >&2
    else
      # Same password-persistence reasoning as before: the password is set
      # into the store itself on first init and must match on every later
      # restart against the same (persistent) data. set-initial-password
      # only works before the store has ever started once, so guard it
      # with our own marker rather than depending on neo4j-admin's own
      # error behavior on a repeat call against an already-initialized store.
      if [ -f "$NEO4J_PASSWORD_FILE" ]; then
        NEO4J_PW="$(cat "$NEO4J_PASSWORD_FILE")"
      else
        NEO4J_PW="$("$FISHERY_VENV/bin/python3" -c 'import secrets; print(secrets.token_urlsafe(24))')"
        echo -n "$NEO4J_PW" > "$NEO4J_PASSWORD_FILE"
        chmod 600 "$NEO4J_PASSWORD_FILE"
      fi

      if [ ! -f "$NEO4J_INIT_MARKER" ]; then
        if NEO4J_HOME="$NEO4J_HOME" "$NEO4J_HOME/bin/neo4j-admin" dbms set-initial-password "$NEO4J_PW"; then
          touch "$NEO4J_INIT_MARKER"
        else
          echo "neo4j-admin dbms set-initial-password failed — continuing without" >&2
          echo "the memory layer (NEO4J_URI stays unset)." >&2
        fi
      fi

      if [ -f "$NEO4J_INIT_MARKER" ]; then
        # Stop any leftover process from a previous killed/crashed job
        # first — bin/neo4j start refuses to start if a stale PID file
        # from an unclean shutdown makes it think an instance is already
        # running.
        NEO4J_HOME="$NEO4J_HOME" "$NEO4J_HOME/bin/neo4j" stop >/dev/null 2>&1 || true
        echo "Starting Neo4j (portable binary, no container)..."
        if NEO4J_HOME="$NEO4J_HOME" "$NEO4J_HOME/bin/neo4j" start; then
          neo4j_ready=0
          for _ in $(seq 1 60); do
            if (exec 3<>/dev/tcp/127.0.0.1/7687) 2>/dev/null; then
              exec 3<&- 3>&- 2>/dev/null || true
              neo4j_ready=1
              break
            fi
            sleep 2
          done

          if [ "$neo4j_ready" = "1" ]; then
            export NEO4J_URI="bolt://localhost:7687"
            export NEO4J_USER="neo4j"
            export NEO4J_PASSWORD="$NEO4J_PW"
            echo "Neo4j reachable at $NEO4J_URI — memory layer enabled for this run."
            # Stop it when this script exits, success or failure — SLURM
            # would eventually clean up the job's process group regardless,
            # but an explicit stop avoids leaving a stale PID file for the
            # next job's own 'bin/neo4j start' to trip over.
            _stop_neo4j() { NEO4J_HOME="$NEO4J_HOME" "$NEO4J_HOME/bin/neo4j" stop >/dev/null 2>&1 || true; }
            trap _stop_neo4j EXIT
          else
            echo "Neo4j process started but 127.0.0.1:7687 never became reachable" >&2
            echo "within 120s — continuing without the memory layer (NEO4J_URI" >&2
            echo "stays unset)." >&2
            NEO4J_HOME="$NEO4J_HOME" "$NEO4J_HOME/bin/neo4j" stop >/dev/null 2>&1 || true
          fi
        else
          echo "'neo4j start' failed — continuing without the memory layer" >&2
          echo "(NEO4J_URI stays unset)." >&2
        fi
      fi
    fi
  fi
fi

# Understand-Anything: a semantic ("what is this for") complement to
# CodeGraph's structural ("what calls what") index — see CLAUDE.md's
# "Understand-Anything" section. Opt-in, off by default: unlike codegraph
# init (a few seconds, zero LLM calls, pure parsing), building this graph
# means opencode dispatching a real subagent per batch of files across the
# whole repo — genuine LLM time on the same GPU the fisher/norm-implementer
# calls already share, not something every ordinary run should pay for.
# Set BUILD_KNOWLEDGE_GRAPH=1 to opt in. This is only the ONE-TIME initial
# build; engine/simulate.py's refresh_knowledge_graph() does the ongoing
# per-round incremental refresh after that, reading this same env var —
# without it, the graph built here would just go stale round after round
# as norms/*.py changes, same problem CodeGraph had before its own
# per-round refresh got added to PHASE 2 above.
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

  # install.sh's cmd_install() only git-clones the repo and symlinks skill
  # files — read directly, it never runs `pnpm install`. That means the
  # plugin's compiled core (understand-anything-plugin/packages/core/dist/
  # index.js, produced by the *root* package.json's own `"prepare": "pnpm
  # --filter @understand-anything/core build"` lifecycle script, which only
  # fires on a real `pnpm install`) is never actually built by the installer
  # on its own. Confirmed as a real, repeatable gap across two separate
  # real opencode sessions, not a one-off: one where the build agent tried to
  # self-repair it (correctly ran `pnpm install && pnpm build` itself) and got
  # silently permission-denied — the reason --auto exists below — and a
  # second, later session where it didn't even attempt a self-repair and
  # generate-ignore.mjs just crashed with ERR_MODULE_NOT_FOUND importing the
  # never-built dist/index.js. Two different failure shapes from the same
  # root cause is a sign this shouldn't be left to an LLM session to notice
  # and fix each time — it's a deterministic, non-LLM step, so do it directly
  # here instead of inside the opencode subprocess below.
  # Don't hardcode one assumed layout — a real Aoraki run showed the
  # installed plugin actually lives at $HOME/.understand-anything-plugin
  # directly, NOT nested under $HOME/.understand-anything/repo/
  # understand-anything-plugin/ the way install.sh's own documented
  # REPO_DIR default (and this script's own earlier assumption) implied.
  # Check both: whichever one actually has a package.json is the real one.
  UA_REPO_DIR=""
  UA_CORE_DIST=""  # stays empty (never a real file) if no plugin root is found below —
                    # must be defined unconditionally: set -u would otherwise crash the
                    # whole job on the fail-fast check further down that reads it.
  for candidate in \
    "$HOME/.understand-anything-plugin" \
    "$HOME/.understand-anything/repo/understand-anything-plugin"; do
    if [ -f "$candidate/package.json" ]; then
      UA_REPO_DIR="$candidate"
      break
    fi
  done

  if [ -n "$UA_REPO_DIR" ]; then
    UA_CORE_DIST="$UA_REPO_DIR/packages/core/dist/index.js"
    if [ ! -f "$UA_CORE_DIST" ]; then
      echo "Understand-Anything core not built at $UA_REPO_DIR — running pnpm install (its 'prepare' script builds the core)"
      # corepack ships with Node >=16.9 but needs an explicit 'enable' to
      # actually create the pnpm shim alongside node's own binary — a real
      # run showed `node -v` working but `pnpm -v` failing as "command not
      # found" in the exact same shell, which is what a never-enabled
      # corepack looks like. Idempotent and safe to call unconditionally.
      command -v corepack >/dev/null 2>&1 && corepack enable >/dev/null 2>&1
      if command -v pnpm >/dev/null 2>&1; then
        ( cd "$UA_REPO_DIR" && pnpm install ) || \
          echo "pnpm install failed in $UA_REPO_DIR — continuing; the build-agent invocation below will fail fast on the same missing dist/index.js and fall through to the graceful-skip path" >&2
      else
        echo "pnpm still not found on this node after 'corepack enable' — Understand-Anything's core can't be built; continuing without it (graceful-skip path below)" >&2
      fi
    fi
  else
    echo "No Understand-Anything plugin checkout found under \$HOME (checked" >&2
    echo "$HOME/.understand-anything-plugin and $HOME/.understand-anything/repo/" >&2
    echo "understand-anything-plugin) — the skill install above may have used a" >&2
    echo "different layout than either. Continuing without building the core;" >&2
    echo "the build-agent invocation below will fall through to the graceful-skip path." >&2
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
  #
  # --command understand, not a natural-language "Run /understand ..."
  # message: a real run on gpt-oss-120b confirmed the smaller local model
  # doesn't reliably infer "this is a skill, read SKILL.md and execute its
  # steps yourself" from prose — it tried to find and run a literal
  # `understand` binary instead (`command not found`), then gave up and
  # printed manual install instructions without ever touching the actual
  # pipeline, leaving no .ua/ directory at all despite reporting no error to
  # this script (opencode's own exit code was 0 — a "successful" no-op).
  # `opencode run --command <name>` invokes the named skill/command
  # directly and structurally — confirmed to be accepted syntax locally
  # (reached the auth step, not an argument-parsing error) — instead of
  # depending on the model correctly inferring skill intent from a message.
  # Arguments after -- go to the skill as $ARGUMENTS, same as SKILL.md's
  # own documented parsing (a single string it greps for flags in, not an
  # argv array), matching how --full/--no-auto-update are described there.
  #
  # Trailing message required too — a real run confirmed --command alone
  # loads the skill into context and then just stops ("The understand
  # skill is now loaded and ready. Let me know what you'd like to do"),
  # never executing a single phase, still exit 0. --command answers "what
  # skill" but apparently not "go run it now" on its own; an explicit
  # directive is still needed alongside it. Confirmed locally to still be
  # accepted syntax (reaches the auth step) with both present.
  #
  # --auto matters too, found later the same day: with --format json
  # actually capturing real diagnostics (see refresh_knowledge_graph()),
  # a real log showed the model correctly diagnosing "need to build core"
  # and issuing exactly the right `pnpm install && pnpm build` command —
  # which then got denied: "The user rejected permission to use this
  # specific tool call." The build agent's external_directory permission
  # defaults to "ask", and the plugin's own checkout
  # ($HOME/.understand-anything/repo/...) is outside the project
  # directory — headless, no one to answer, so it silently auto-denies.
  # --auto ("auto-approve permissions that are not explicitly denied") is
  # opencode's own documented mechanism for exactly this unattended case.
  #
  # Generous timeout, not a tight one: unverified how long a real run takes
  # here — if it's still stuck, fail this step loudly and continue without
  # a graph (norm-implementer's PHASE 2 already treats a missing graph as
  # non-blocking — falls back to CodeGraph + direct reading), exactly like
  # codegraph's own graceful-degradation pattern above, rather than eating
  # the rest of this job's wall time.
  build_failed=0
  # Fail fast instead of paying the 1800s timeout (and the GPU/model time it
  # burns, shared with the fisher/norm-implementer calls) for a run that's
  # already known to hit the same ERR_MODULE_NOT_FOUND the pnpm-install step
  # above just tried to prevent — e.g. pnpm wasn't found on this node, or
  # `pnpm install` itself failed.
  if [ ! -f "$UA_CORE_DIST" ]; then
    echo "Understand-Anything core still missing at $UA_CORE_DIST after the pnpm install attempt — skipping the opencode build call entirely rather than spending 1800s on a run that would fail the same way" >&2
    build_failed=1
  elif ! timeout 1800 opencode run --agent build --model "$OPENCODE_MODEL" --auto \
    --command understand -- "--full --no-auto-update" \
    "Begin the analysis immediately, following the skill's own instructions completely — do not wait for further input." \
    > logs/understand-anything-build.log 2>&1; then
    build_failed=1
  fi
  # Exit code alone isn't trustworthy here — a real run returned 0 while
  # having done nothing at all (gave up internally, printed advice, never
  # wrote anything). Verify the actual claimed outcome instead of just the
  # process's own report of it.
  if [ ! -f .ua/knowledge-graph.json ] && [ ! -f .understand-anything/knowledge-graph.json ]; then
    build_failed=1
  fi
  if [ "$build_failed" = "1" ]; then
    echo "Understand-Anything build didn't finish within 1800s, failed, or" >&2
    echo "produced no knowledge-graph.json despite exiting cleanly — see" >&2
    echo "logs/understand-anything-build.log. Continuing without a knowledge" >&2
    echo "graph: the norm-implementer will fall back to CodeGraph + direct" >&2
    echo "reading, which still works, just without the semantic view." >&2
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
