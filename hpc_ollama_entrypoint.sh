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

# codegraph: same problem as opencode above (installed but not on PATH here)
# would apply, plus it was never installed here at all yet — the earlier
# `npm install -g` route used to set this up doesn't apply on a node that
# likely has no Node.js. This installer is Node-free (a self-contained
# bundle) and puts a symlink in ~/.local/bin by default.
export PATH="$HOME/.local/bin:$PATH"
if ! command -v codegraph >/dev/null 2>&1; then
  echo "codegraph not found (checked \$HOME/.local/bin) — installing there"
  curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh
fi

# --no-color, telemetry off: codegraph's default output uses cursor-control
# ANSI codes meant for a live TTY (spinners etc.) — dumped into a SLURM log
# file instead of a real terminal, that just accumulates as garbled control
# sequences, not a hang by itself, but makes the log unreadable and makes an
# actual hang harder to see. Telemetry is an outbound network call on
# init/sync (see https://github.com/colbymchenry/codegraph/blob/main/TELEMETRY.md);
# disabling it removes one plausible hang source on a node with restricted
# internet.
export CODEGRAPH_TELEMETRY=0

# .codegraph/ is a local, per-checkout index — never committed to git (see
# .gitignore) — so it doesn't exist yet on a fresh clone of this repo, which
# is exactly the situation on a cluster you haven't run this on before.
# Without it, opencode.jsonc's codegraph MCP server finds no index and
# exposes no tools at all, and the norm-implementer silently falls back to
# plain Read/Grep instead of codegraph_explore — no error, just quietly
# worse exploration. Build it once, then keep it current on every later run.
#
# unlock first: codegraph has its own documented failure mode of "a stale
# lock file blocking indexing" (codegraph unlock exists specifically for
# this) — a real risk here given how many times this job has been killed
# and resubmitted while debugging the earlier failures above. Safe to run
# even if nothing is actually locked.
codegraph --no-color unlock . 2>&1 || true

echo "Making sure this checkout has a CodeGraph index..."
if [ -d .codegraph ]; then
  CODEGRAPH_CMD="sync"
else
  CODEGRAPH_CMD="init"
fi
# Wrapped in a hard timeout: if it's still stuck for some other reason, fail
# loudly and say so, rather than silently eating the rest of the job's wall
# time. codegraph init/sync on this repo's ~15 files took under a second
# when this was verified locally, so 120s is already a generous margin, not
# a tight one.
if ! timeout 120 codegraph --no-color "$CODEGRAPH_CMD" .; then
  echo "codegraph $CODEGRAPH_CMD didn't finish within 120s — either genuinely" >&2
  echo "hung (check for network calls it can't complete, or run 'codegraph" >&2
  echo "unlock .' by hand and retry) or failed outright. Continuing without a" >&2
  echo "CodeGraph index: the norm-implementer will fall back to plain" >&2
  echo "Read/Grep, which still works, just with worse exploration." >&2
fi

# The fisher agent no longer goes through opencode — llm_agents.py calls
# litellm directly. litellm's response types use pydantic forward
# references that need a matching pydantic (and pydantic's own compiled
# pydantic-core) to resolve, or construction fails with "Message is not
# fully defined ... call Message.model_rebuild()".
#
# Ruled out on 2026-08-19: this isn't system-vs-user site-packages
# shadowing — the exact same failure reproduced inside a from-scratch
# isolated venv, with litellm and pydantic both confirmed resolving from
# that venv's own site-packages, nothing external involved. What was still
# unpinned was pydantic-core itself: pip was free to resolve whatever
# pydantic-core paired with pydantic==2.13.4 on Aoraki's Python 3.10/Linux,
# and apparently got something other than the pydantic-core==2.46.4 that
# macOS/Python 3.11 resolved and was actually verified end-to-end here.
# Pinning all three removes that ambiguity.
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
  litellm==1.97.0 pydantic==2.13.4 pydantic-core==2.46.4 python-dotenv

# Reproduce the exact failure point from the 2026-08-19 incident
# (ModelResponse() construction) right here, so a version mismatch fails
# loudly before round 1 rather than three silent retries into it. Not
# suppressing output this time — if this still fails, the traceback and
# diagnostics below are what's needed to actually root-cause it further.
if ! "$FISHERY_VENV/bin/python3" -c "from litellm.types.utils import ModelResponse; ModelResponse()"; then
  echo "Still broken even with litellm/pydantic/pydantic-core all pinned and" >&2
  echo "identical to a known-working install elsewhere — so it's a transitive" >&2
  echo "dependency (typing_extensions/openai/httpx/etc., none pinned) resolving" >&2
  echo "differently here. Full dependency tree for a direct diff:" >&2
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
# Run through the venv's interpreter, not the container's bare python3 —
# that's the whole point of building it above. simulate.py itself and
# everything it imports besides llm_agents.py (call_log, mechanisms/*,
# phases/*) is stdlib-only, so this venv (litellm/pydantic/python-dotenv
# only, no --system-site-packages) has everything the run needs; the
# opencode subprocess call for the norm-implementer is an external binary,
# unaffected by which Python interpreter launched it.
"$FISHERY_VENV/bin/python3" simulate.py --max-rounds "${MAX_ROUNDS:-20}"
