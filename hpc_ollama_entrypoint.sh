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

echo "Checking gpt-oss:120b is present under OLLAMA_MODELS=${OLLAMA_MODELS:-<unset>} (not downloading it)..."
if ! ollama list | grep -q "gpt-oss:120b"; then
  echo "gpt-oss:120b not found via 'ollama list'. You said this is already" >&2
  echo "downloaded manually — check OLLAMA_MODELS points at the right directory," >&2
  echo "or run 'ollama list' yourself in this same environment to see what tag" >&2
  echo "it's actually registered under." >&2
  exit 1
fi
echo "Found gpt-oss:120b."

# Ollama caps every model's context window at 4096 tokens by default,
# regardless of what the model itself supports (gpt-oss:120b advertises
# 128K) — confirmed elsewhere to fail *silently* when exceeded: a response
# with only reasoning tokens and no actual answer, not a clear error. That's
# very likely what the earlier "no JSON object found in agent response: ''"
# retries were actually hitting, not a random transient hiccup — this
# repo's prompts grow every round (history window, codegraph_explore
# output). Create an extended-context variant rather than relying on the
# 4096 default. Override OLLAMA_NUM_CTX if 32768 isn't enough.
OLLAMA_NUM_CTX="${OLLAMA_NUM_CTX:-32768}"
OLLAMA_CTX_MODEL_ID="gpt-oss-120b-${OLLAMA_NUM_CTX}ctx"
echo "Creating extended-context variant ${OLLAMA_CTX_MODEL_ID} (num_ctx=${OLLAMA_NUM_CTX})..."
printf 'FROM gpt-oss:120b\nPARAMETER num_ctx %s\n' "$OLLAMA_NUM_CTX" > /tmp/fishery.Modelfile
ollama create "$OLLAMA_CTX_MODEL_ID" -f /tmp/fishery.Modelfile

# Point opencode's "ollama" provider at THIS job's actual (randomly-assigned)
# port instead of the committed opencode.jsonc's fixed 127.0.0.1:11434
# default. .opencode/opencode.json is gitignored — opencode merges it in
# automatically as an extra project-local config layer, nothing tracked
# gets touched.
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
        "${OLLAMA_CTX_MODEL_ID}": { "name": "GPT-OSS 120B, ${OLLAMA_NUM_CTX}-token context (Aoraki Ollama)" }
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
# litellm directly. Same on-demand install pattern as opencode/codegraph
# above, since this container image predates that change.
if ! python3 -c "import litellm" >/dev/null 2>&1; then
  echo "litellm not found in this container's Python — installing"
  pip install --quiet litellm python-dotenv
fi

mkdir -p logs
# OPENCODE_MODEL still drives the norm-implementer (still an opencode agent).
# FISHER_MODEL drives the fisher's direct litellm calls. Same underlying
# model, two separate call paths reading two separate env vars.
export OPENCODE_MODEL="ollama/${OLLAMA_CTX_MODEL_ID}"
export FISHER_MODEL="ollama/${OLLAMA_CTX_MODEL_ID}"
python3 simulate.py --max-rounds "${MAX_ROUNDS:-20}"
