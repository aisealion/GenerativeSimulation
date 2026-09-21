#!/bin/bash
# Runs *inside* the apptainer container's environment — this is the command
# run_simulation.slurm hands to `apptainer run` after it starts the ollama
# server and exports OLLAMA_HOST, not something you run directly.
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

# This repo is small, and reload_project_modules() (engine/simulate.py)
# already forces every changed module to be re-imported fresh every
# round regardless of what's cached on disk — the .pyc bytecode cache
# Python would otherwise write to a __pycache__/ beside every .py file
# buys essentially nothing here, and was a real, repeated nuisance: the
# norm-implementer/norm-evaluator/norm-finalizer agents' own read/glob
# tools kept surfacing these as if they were real files to inspect.
# Exported once, here, so every Python process this job ever spawns
# (this script's own one-off python3 calls, the main `python3 -m
# engine.simulate` invocation below, and every fresh validation
# subprocess engine/simulate.py spawns via subprocess.run([sys.executable,
# ...])) inherits it and never writes one in the first place —
# engine/simulate.py's own clean_pycache_dirs() (called every round) is
# just the defense-in-depth backstop for whatever's already on disk from
# before this was set.
export PYTHONDONTWRITEBYTECODE=1

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
# norm pipeline agents' (norm-architect/norm-engineer/norm-auditor)
# codegraph_explore/impact/callers MCP tool calls are always current
# without anyone explicitly re-running init/sync per round (that manual
# per-round refresh — see each agent's own codebase-understanding step in
# .opencode/agent/ — was itself only ever a workaround for not trusting
# this path).
# Deliberately not the same thing as the original incident: that was
# specifically `codegraph sync` invoked as a one-shot CLI command outside
# the daemon's own control (its docs describe sync as normally
# daemon-triggered, not meant to be run directly) — the daemon *itself* was
# separately tested and cleared by direct reproduction (see above), it was
# only ever left off out of low-cost caution, not because it was the
# confirmed cause. Still, this is a real, not-fully-eliminated risk in the
# specific repeated-across-many-rounds production context that standalone
# reproduction never exercised — engine/simulate.py's run_norm_engineer()
# (run_norm_implementer() at the time) was hardened the same day to catch
# a hung/failed opencode invocation and discard that round rather than
# crash the whole multi-round run, so a recurrence here costs one round,
# not the rest of the job. Re-add `export CODEGRAPH_NO_DAEMON=1` above to
# revert to the previous manual-refresh-only behavior if this turns out to
# still be the cause.

# .codegraph/ is a local, per-checkout index — never committed to git (see
# .gitignore) — so it doesn't exist yet on a fresh clone of this repo, which
# is exactly the situation on a cluster you haven't run this on before.
# Without it, opencode.jsonc's codegraph MCP server finds no index and
# exposes no tools at all, and the norm pipeline agents silently fall back
# to plain Read/Grep instead of codegraph_explore — no error, just quietly
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
  echo "the norm pipeline agents will fall back to plain Read/Grep, which still works," >&2
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

# Two base tags for the norm pipeline's reasoning/audit and engineering
# roles (2026-09-21: replaced gpt-oss:120b here — norm-architect and
# norm-auditor both route to DeepSeek-R1, norm-engineer routes to
# Qwen3-Coder-Next, per the dual-model/TDD/auditor split — see
# engine/simulate.py's run_norm_architect()/run_norm_engineer()/
# run_norm_auditor()). Parameterized as overridable vars, not hardcoded
# inline, specifically so a real Ollama-registry tag mismatch is a
# one-line fix here rather than a script rewrite.
DEEPSEEK_R1_TAG="${DEEPSEEK_R1_TAG:-deepseek-r1:70b}"
QWEN3_CODER_TAG="${QWEN3_CODER_TAG:-qwen3-coder:30b}"

# Dense 70B (DeepSeek-R1) has all 70B parameters active per token, unlike
# gpt-oss:120b's sparse MoE (far fewer active params despite the larger
# total) — so per-token latency for the architect/auditor role may be
# noticeably different from the old 120b norm-implementer's, not
# necessarily faster just because "70B < 120B." Genuinely open question
# for the first real timed run on this hardware, not asserted either way
# here.
#
# VRAM headroom for this specific model combination (DeepSeek-R1:70b +
# Qwen3-Coder-Next alongside gpt-oss:20b, all swapped on one GPU by
# Ollama) is UNVERIFIED — this repo has never run it. The single-H200
# (144GB) GPU allocation below was sized and confirmed against a
# different pair (gpt-oss:120b + gpt-oss:20b, see run_simulation.slurm's
# own comment); it is not re-confirmed for this new pair. If a real run
# OOMs, the documented first fallback is run_simulation.slurm's
# `--gres=gpu:1` -> `--gres=gpu:2` plus re-adding `OLLAMA_SCHED_SPREAD=1`
# (both explicitly removed-but-available per that file's own history).
#
# Fisher (many small, fast decisions per round — 10 agents x 3 actions)
# still runs on gpt-oss:20b, untouched by this change. All three model
# tags must already be present — same never-auto-pull policy as before,
# just checked three times now instead of twice.
for MODEL_TAG in "gpt-oss:20b" "$DEEPSEEK_R1_TAG" "$QWEN3_CODER_TAG"; do
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
# regardless of what the model itself supports — confirmed elsewhere to
# fail *silently* when exceeded: a response with only reasoning tokens and
# no actual answer, not a clear error. That's very likely what the earlier
# "no JSON object found in agent response: ''" retries were actually
# hitting, not a random transient hiccup — this repo's prompts grow every
# round (history window, codegraph_explore output, and now a 10-agent
# proposals list for the vote action). Create an extended-context variant
# of each model rather than relying on the 4096 default.
#
# Three independent context sizes, not one shared value: the architect's
# and engineer's sessions accumulate a long multi-turn tool-call history
# (a real session has hit 80+ tool calls) and benefit from real headroom;
# the 20b fisher makes far more calls per round (up to agent_count x ~4)
# but each one is a single short persona+action prompt with no growing
# tool-call history, so doubling its context too would just cost KV-cache
# memory on every one of those many calls for no benefit. Override any of
# the three independently if needed.
#
# 2026-09-21: norm-architect/norm-auditor (deepseek-r1) and norm-engineer
# (qwen3-coder) sizes are no longer copied from gpt-oss:120b's own 131072
# figure — that was a different architecture with its own advertised
# ceiling. Real per-model numbers (see opencode.jsonc's own comment for
# sourcing):
#   - deepseek-r1:70b is a Llama-3.3-70B distillation: advertises a 128K
#     ceiling, but real-world reports (Ollama's own community guidance,
#     multiple hosted-API providers) converge on noticeably degraded
#     quality well before that, and its own long chain-of-thought
#     reasoning competes with output for the same context budget. 64K
#     context / 32K output is a middle ground actually exercised
#     elsewhere (Azure AI Foundry, AWS Bedrock both cap DeepSeek-R1
#     output at 32768).
#   - qwen3-coder:30b (a sparse MoE, ~3B active params) natively supports
#     262144 (256K) — over 2x gpt-oss:120b's 131072 — but kept at 131072
#     here anyway, deliberately not raised to match its own native
#     ceiling: this repo's real observed need (an agentic session with
#     80+ tool calls) was satisfied by 131072 for the analogous role
#     (gpt-oss:120b), and doubling context would double this model's own
#     KV-cache VRAM cost for no demonstrated benefit, compounding the
#     already-unverified VRAM headroom noted above for this new model
#     combination. Output raised to 65536, the model's own documented
#     "recommended max" (vs. 32768 "standard") — code-generation turns
#     can produce large multi-file diffs in one response.
# num_predict (separate from num_ctx) caps a single response's own length
# — Ollama's Modelfile PARAMETER for what other APIs call max_tokens/
# max_output_tokens. Previously left unset for gpt-oss:120b/20b (Ollama's
# own default there is effectively "until num_ctx is exhausted"); set
# explicitly here since DeepSeek-R1's long reasoning traces and
# Qwen3-Coder's own documented output ceiling are both real, provider-
# recommended limits distinct from their context windows, not just
# "whatever's left of num_ctx."
OLLAMA_NUM_CTX_20B="${OLLAMA_NUM_CTX_20B:-32768}"
OLLAMA_NUM_CTX_ARCHITECT="${OLLAMA_NUM_CTX_ARCHITECT:-65536}"
OLLAMA_NUM_PREDICT_ARCHITECT="${OLLAMA_NUM_PREDICT_ARCHITECT:-32768}"
OLLAMA_NUM_CTX_ENGINEER="${OLLAMA_NUM_CTX_ENGINEER:-131072}"
OLLAMA_NUM_PREDICT_ENGINEER="${OLLAMA_NUM_PREDICT_ENGINEER:-65536}"
OLLAMA_20B_CTX_MODEL_ID="gpt-oss-20b-${OLLAMA_NUM_CTX_20B}ctx"
OLLAMA_ARCHITECT_CTX_MODEL_ID="deepseek-r1-70b-${OLLAMA_NUM_CTX_ARCHITECT}ctx"
OLLAMA_ENGINEER_CTX_MODEL_ID="qwen3-coder-30b-${OLLAMA_NUM_CTX_ENGINEER}ctx"

echo "Creating extended-context variant ${OLLAMA_20B_CTX_MODEL_ID} (num_ctx=${OLLAMA_NUM_CTX_20B}) from gpt-oss:20b..."
printf 'FROM gpt-oss:20b\nPARAMETER num_ctx %s\n' "$OLLAMA_NUM_CTX_20B" > /tmp/fishery-20b.Modelfile
ollama create "$OLLAMA_20B_CTX_MODEL_ID" -f /tmp/fishery-20b.Modelfile

# norm-auditor deliberately reuses this same variant (never creates a
# third) — Ollama dedups layers by hash, so this costs no extra disk/VRAM,
# and "never let the model that wrote the code approve its own work" is
# already satisfied by never sharing an opencode --session between agent
# types, independent of whether the auditor's tag matches the architect's.
echo "Creating extended-context variant ${OLLAMA_ARCHITECT_CTX_MODEL_ID} (num_ctx=${OLLAMA_NUM_CTX_ARCHITECT}, num_predict=${OLLAMA_NUM_PREDICT_ARCHITECT}) from ${DEEPSEEK_R1_TAG}..."
printf 'FROM %s\nPARAMETER num_ctx %s\nPARAMETER num_predict %s\n' \
  "$DEEPSEEK_R1_TAG" "$OLLAMA_NUM_CTX_ARCHITECT" "$OLLAMA_NUM_PREDICT_ARCHITECT" > /tmp/fishery-architect.Modelfile
ollama create "$OLLAMA_ARCHITECT_CTX_MODEL_ID" -f /tmp/fishery-architect.Modelfile

echo "Creating extended-context variant ${OLLAMA_ENGINEER_CTX_MODEL_ID} (num_ctx=${OLLAMA_NUM_CTX_ENGINEER}, num_predict=${OLLAMA_NUM_PREDICT_ENGINEER}) from ${QWEN3_CODER_TAG}..."
printf 'FROM %s\nPARAMETER num_ctx %s\nPARAMETER num_predict %s\n' \
  "$QWEN3_CODER_TAG" "$OLLAMA_NUM_CTX_ENGINEER" "$OLLAMA_NUM_PREDICT_ENGINEER" > /tmp/fishery-engineer.Modelfile
ollama create "$OLLAMA_ENGINEER_CTX_MODEL_ID" -f /tmp/fishery-engineer.Modelfile

# Point opencode's "ollama" provider at THIS job's actual (randomly-assigned)
# port instead of the committed opencode.jsonc's fixed 127.0.0.1:11434
# default. .opencode/opencode.json is gitignored — opencode merges it in
# automatically as an extra project-local config layer, nothing tracked
# gets touched. Only the architect/engineer context variants need to be
# listed here — the fisher no longer goes through opencode at all (see
# below), so opencode never needs to know about the 20b model.
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
        "${OLLAMA_ARCHITECT_CTX_MODEL_ID}": {
          "name": "DeepSeek-R1 70B, ${OLLAMA_NUM_CTX_ARCHITECT}-token context (Aoraki Ollama)",
          "limit": { "context": ${OLLAMA_NUM_CTX_ARCHITECT}, "output": ${OLLAMA_NUM_PREDICT_ARCHITECT} }
        },
        "${OLLAMA_ENGINEER_CTX_MODEL_ID}": {
          "name": "Qwen3-Coder-Next, ${OLLAMA_NUM_CTX_ENGINEER}-token context (Aoraki Ollama)",
          "limit": { "context": ${OLLAMA_NUM_CTX_ENGINEER}, "output": ${OLLAMA_NUM_PREDICT_ENGINEER} }
        }
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

mkdir -p ops/logs
# FISHER_MODEL drives the fisher's direct litellm calls — stays the local
# Ollama 20b model (up to agent_count x 3 calls per round, so it needs to
# be the fast/local one). Untouched by the 2026-09-21 dual-model/TDD/
# auditor split below.
#
# NORM_ARCHITECT_MODEL / NORM_ENGINEER_MODEL / NORM_AUDITOR_MODEL route
# the norm pipeline's three opencode agents independently as of
# 2026-09-21 (previously a single NORM_IMPLEMENTER_MODEL shared by
# norm-implementer and norm-evaluator both) — norm-architect and
# norm-auditor to DeepSeek-R1 (reasoning/audit), norm-engineer to
# Qwen3-Coder-Next (execution). engine/simulate.py's own model-selection
# still falls back to NORM_IMPLEMENTER_MODEL/OPENCODE_MODEL if any of the
# three new vars is unset, for anyone running this outside a freshly
# updated entrypoint — but this script always sets all three explicitly.
#
# Prior history, when this was one shared model for both agents: litellm/
# Kimi-K2.5 -> local gpt-oss-120b (2026-09-04, Kimi-K2.5 quota exhausted)
# -> litellm/Kimi-K2.5 again (2026-09-10, after a 12-round local run
# showed its own real reliability cost: roughly half of all
# norm-implementer invocations never reached a genuine stop, and 3 calls
# hung for their full timeout with zero output). Back to local
# gpt-oss-120b again (2026-09-11), after the litellm path failed even
# harder in the very next real run: round 1 completed fine (654s, 82 tool
# calls, a real genuine stop), then every single implementer call from
# round 2 onward — 6 in a row across 3 rounds — hung for the exact full
# 3600s timeout with zero output. Not a gradual flakiness pattern like the
# local model's; a hard, total, starts-at-one-clean-point failure,
# consistent with the Otago proxy hitting a quota/rate limit or going
# unresponsive partway through round 1's own real usage (98 tool-call
# round-trips), with opencode's own retry/backoff against that stuck
# rather than failing fast. Both local and remote paths had a real,
# directly-observed failure mode on record — the same tradeoff applies to
# each of the three vars below independently now.
#
export NORM_ARCHITECT_MODEL="ollama/${OLLAMA_ARCHITECT_CTX_MODEL_ID}"
export NORM_AUDITOR_MODEL="ollama/${OLLAMA_ARCHITECT_CTX_MODEL_ID}"
export NORM_ENGINEER_MODEL="ollama/${OLLAMA_ENGINEER_CTX_MODEL_ID}"
# Ultimate fallback, kept for engine/simulate.py's own env-var fallback
# chain (NORM_ARCHITECT_MODEL/NORM_ENGINEER_MODEL/NORM_AUDITOR_MODEL, each
# falling back through NORM_IMPLEMENTER_MODEL, to this) — this script
# itself never relies on the fallback since it sets all three above.
export OPENCODE_MODEL="ollama/${OLLAMA_ARCHITECT_CTX_MODEL_ID}"
export FISHER_MODEL="ollama/${OLLAMA_20B_CTX_MODEL_ID}"

# Only actually required when one of the norm-pipeline model vars above is
# routed through the Otago LiteLLM proxy — matched generically (litellm/*)
# rather than hardcoding "Kimi-K2.5" so this check stays correct
# regardless of which litellm-hosted model it's pointed at later. Checked
# per-var now (2026-09-21) rather than against one shared
# NORM_IMPLEMENTER_MODEL, since the three roles can each be pointed at a
# different provider independently — a single-var check would silently
# miss any of the other two being routed to litellm. A hard requirement
# here made sense when every run always needed it; it doesn't anymore now
# that the default is a local model needing no key at all — this used to
# unconditionally exit 1 even when nothing in the run actually depended on
# LITELLM_API_KEY.
for VAR_NAME in NORM_ARCHITECT_MODEL NORM_ENGINEER_MODEL NORM_AUDITOR_MODEL; do
  case "${!VAR_NAME}" in
    litellm/*)
      if [ -z "${LITELLM_API_KEY:-}" ]; then
        echo "${VAR_NAME}=${!VAR_NAME} but LITELLM_API_KEY isn't set in this job's" >&2
        echo "environment — every round's call routed through it would fail. sbatch" >&2
        echo "propagates the submitting shell's environment by default, so export" >&2
        echo "LITELLM_API_KEY before running sbatch, or pass it explicitly:" >&2
        echo "sbatch --export=ALL,LITELLM_API_KEY=... run_simulation.slurm" >&2
        exit 1
      fi
      ;;
  esac
done

# Neo4j / Graphiti memory layer (engine/memory/) — previously "local-only
# infra, never deployed on Aoraki" (see CLAUDE.md), by design: nothing here
# ever set NEO4J_URI, and write_memory_episodes()/render_relevant_memories()
# both check `if not os.environ.get("NEO4J_URI")` before touching anything
# memory-related, so its absence was always a silent, correct no-op rather
# than a crash. Opt-in now via ENABLE_NEO4J_MEMORY=1 (off by default — real
# new failure surface and job-startup latency, not something every
# ordinary run should pay for unverified).
#
# 2026-08-28: switched from a nested-Apptainer-instance approach to a
# portable binary run as a plain background process instead — a real job
# confirmed the `apptainer` binary simply isn't reachable inside
# ollama_shellenv.sif at all, so nested container orchestration was a dead
# end on this specific image, not something worth retrying. This mirrors
# how Ollama itself already runs inside this same container: a plain
# server process, not a nested container. Real new dependency this
# approach introduces: Java 17+ must be reachable inside the container
# (Neo4j 5.x's requirement) — confirmed 2026-09-02, on a real job, to
# actually be missing ("no 'java' binary is reachable inside this
# container"), not just unconfirmed as this comment previously said.
if [ "${ENABLE_NEO4J_MEMORY:-0}" = "1" ]; then
  # A `java` binary existing, being executable, AND passing `java -version`
  # is STILL not enough to trust it — confirmed on a second real job,
  # after the java-version check below was already added: the exact same
  # "Error loading java.security file" / NoClassDefFoundError in
  # sun.security.jca.Providers crash recurred in neo4j-admin, on a JVM that
  # had already passed `_java_works()`'s `java -version` check moments
  # earlier. Root cause of *that*: `-version` is a trivial JVM-internal
  # operation that never loads a signed jar or does a KeyStore/Provider
  # lookup, so it never actually exercises `Security.initialize()` reading
  # java.security's `include /etc/crypto-policies/back-ends/java.config`
  # (the actual RHEL-container gotcha, still real, still what run_simulation.slurm's
  # `--bind /etc/crypto-policies` is for) — it was testing the wrong thing
  # entirely, not almost-but-not-quite the right thing. `neo4j-admin`
  # crashes because verifying its own jars' signatures *does* trigger that
  # path. `keytool -list` against a bogus keystore triggers the identical
  # provider-lookup path (KeyStore.getInstance() always needs one) even
  # though the keystore itself doesn't exist — so a real security-init
  # crash and a benign "keystore not found" failure are distinguishable by
  # matching the actual crash signature in keytool's own stderr, not by
  # exit code alone (both fail non-zero).
  _java_works() {
    command -v java >/dev/null 2>&1 || return 1
    java -version >/dev/null 2>&1 || return 1
    command -v keytool >/dev/null 2>&1 || return 1
    local keytool_out
    keytool_out=$(keytool -list -keystore /nonexistent-keystore -storepass x 2>&1) || true
    if echo "$keytool_out" | grep -qiE "Error loading java\.security|NoClassDefFoundError|ExceptionInInitializerError"; then
      return 1
    fi
    return 0
  }

  if ! _java_works; then
    # First choice: the host's own JVM, exposed into the container via
    # run_simulation.slurm's --bind /usr/lib/jvm (added 2026-09-02 once a
    # real login-node check found java-17-openjdk-17.0.20.0.8-1.2.el9_8.x86_64
    # already installed there as a plain OS package — no JAVA_HOME/module
    # involved). No network needed if this is present and actually works.
    # Glob rather than a hardcoded version string, since that exact
    # package version will change under a routine OS update outside this
    # project's control — matches java-17-openjdk* specifically first
    # (this project only needs 17+, and that's the confirmed real package
    # name pattern), then any JVM under /usr/lib/jvm as a looser second
    # attempt. Left as literal, non-matching glob text (not an error) if
    # /usr/lib/jvm doesn't exist on whatever node this job actually lands
    # on — the `-x` test below just says no on a literal unexpanded
    # pattern, same as any other missing path.
    HOST_JVM_JAVA=""
    for candidate in /usr/lib/jvm/java-17-openjdk*/bin/java /usr/lib/jvm/*/bin/java; do
      if [ -x "$candidate" ]; then
        HOST_JVM_JAVA="$candidate"
        break
      fi
    done
    if [ -n "$HOST_JVM_JAVA" ]; then
      JAVA_HOME="$(dirname "$(dirname "$HOST_JVM_JAVA")")"
      export JAVA_HOME
      export PATH="$JAVA_HOME/bin:$PATH"
      if _java_works; then
        echo "Found a working host JVM via the /usr/lib/jvm bind mount: $JAVA_HOME"
      else
        echo "Found a host JVM at $JAVA_HOME but 'java -version' fails there —" >&2
        echo "likely the RHEL crypto-policies container gotcha (missing" >&2
        echo "/etc/crypto-policies inside the container). Falling back to the" >&2
        echo "portable JRE download instead of trusting this one." >&2
        unset JAVA_HOME
      fi
    fi
  fi

  if ! _java_works; then
    # Fallback: no working host JVM found (bind missing, this compute
    # node's /usr/lib/jvm doesn't match the login node's, or the host JVM
    # exists but doesn't actually run in this container). Same
    # portable-binary philosophy as Neo4j's own download a few lines down:
    # no system install, no root, download+extract+PATH, cached under
    # persistent storage so only the first run ever pays for it. Eclipse
    # Temurin's JRE (not the full JDK — Neo4j only runs on it, never
    # compiles anything) satisfies the same Java 17+ requirement, and
    # isn't RHEL-patched to depend on /etc/crypto-policies the way the
    # host JVM above is, so it shouldn't hit the same failure.
    # URL verified directly (not just assumed): `curl -fsSL` follows
    # Adoptium's own 307->302 redirect chain to a real GitHub release
    # asset (HTTP 200, 46.6MB, application/octet-stream — not an error
    # page), and the tarball's one top-level directory
    # (jdk-17.0.20.1+1-jre/) confirmed to contain bin/java directly, so
    # --strip-components=1 lands it at $JAVA_HOME/bin/java exactly like
    # NEO4J_HOME's own extraction does below.
    JDK_STORE_DIR="/projects/sciences/computing/cranefield_lab/magha601/jdk"
    JAVA_HOME="$JDK_STORE_DIR/jdk-home"
    mkdir -p "$JDK_STORE_DIR"
    if [ ! -x "$JAVA_HOME/bin/java" ]; then
      echo "No working 'java' binary in this container and none cached at" >&2
      echo "$JAVA_HOME — downloading a portable Eclipse Temurin JRE 17" >&2
      echo "(Neo4j 5.x's minimum)."
      JDK_TARBALL_URL="https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jre/hotspot/normal/eclipse"
      JDK_DOWNLOAD_DIR="$JDK_STORE_DIR/download"
      mkdir -p "$JDK_DOWNLOAD_DIR"
      if curl -fsSL "$JDK_TARBALL_URL" -o "$JDK_DOWNLOAD_DIR/jre.tar.gz"; then
        rm -rf "$JAVA_HOME"
        mkdir -p "$JAVA_HOME"
        tar -xzf "$JDK_DOWNLOAD_DIR/jre.tar.gz" -C "$JAVA_HOME" --strip-components=1 || rm -rf "$JAVA_HOME"
      else
        echo "Failed to download a portable JRE from $JDK_TARBALL_URL (egress to" >&2
        echo "api.adoptium.net/github release assets from this compute node is" >&2
        echo "unconfirmed) — continuing without the memory layer (NEO4J_URI stays" >&2
        echo "unset)." >&2
      fi
      rm -rf "$JDK_DOWNLOAD_DIR"
    fi
    if [ -x "$JAVA_HOME/bin/java" ]; then
      export JAVA_HOME
      export PATH="$JAVA_HOME/bin:$PATH"
      if _java_works; then
        echo "Portable JRE ready and verified working at $JAVA_HOME."
      else
        echo "Portable JRE downloaded to $JAVA_HOME but 'java -version' still" >&2
        echo "fails there — something is wrong with this specific build, not" >&2
        echo "just a missing container path. Continuing without the memory" >&2
        echo "layer." >&2
        unset JAVA_HOME
      fi
    fi
  fi

  if ! _java_works; then
    echo "ENABLE_NEO4J_MEMORY=1 but no WORKING java could be found or set up" >&2
    echo "(host JVM missing or broken, portable JRE fetch failed too) —" >&2
    echo "Neo4j 5.x needs Java 17+. Continuing without the memory layer" >&2
    echo "(NEO4J_URI stays unset)." >&2
  else
    # Persistent storage, same convention as OLLAMA_MODELS above: the
    # extracted Neo4j *distribution* (the binaries, not the data) survives
    # across job resubmissions, so only the very first job ever run pays
    # for the download. The *data* is deliberately NOT shared the same
    # way (changed 2026-09-03, by request) — a new sbatch submission is "a
    # new run" and should never see an unrelated earlier run's accumulated
    # graph, so NEO4J_JOB_DATA_DIR below is scoped per $SLURM_JOB_ID (a
    # fresh, empty one every job) rather than the previous single
    # shared-forever data directory. Nothing is ever deleted by this — an
    # old job's data directory just sits on disk under its own job-ID
    # folder, unread by a later job, not wiped. The one real tradeoff:
    # a simulation *resumed* via a brand-new `sbatch` (not the same
    # allocation) picks up state/runtime.json's round progress fine (that's
    # a git-tracked file, unrelated to any of this) but starts the Neo4j
    # memory layer over empty rather than continuing it — chosen
    # deliberately, since "don't reuse an unrelated old run's data" was the
    # explicit ask, and losing memory continuity across a resumed
    # multi-submission run is a smaller cost than that.
    NEO4J_STORE_DIR="/projects/sciences/computing/cranefield_lab/magha601/neo4j"
    NEO4J_HOME="$NEO4J_STORE_DIR/neo4j-home"
    # bin/neo4j resolves `data` (and everything else) relative to
    # NEO4J_HOME by default — no neo4j.conf edit needed, just replace
    # NEO4J_HOME/data with a symlink to this job's own directory before
    # ever starting Neo4j (see below, right before neo4j-admin runs).
    NEO4J_JOB_ID="${SLURM_JOB_ID:-manual-$(date +%Y%m%d-%H%M%S)}"
    NEO4J_JOB_DATA_DIR="$NEO4J_STORE_DIR/data-by-job/$NEO4J_JOB_ID"
    NEO4J_PASSWORD_FILE="$NEO4J_JOB_DATA_DIR/password"
    NEO4J_INIT_MARKER="$NEO4J_JOB_DATA_DIR/.initialized"
    mkdir -p "$NEO4J_STORE_DIR" "$NEO4J_JOB_DATA_DIR"

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
      # Point the shared distribution's data directory at THIS job's own
      # fresh, empty directory before anything (neo4j-admin included) ever
      # reads or writes it. Always reset the symlink rather than checking
      # whether it's already correct — cheap, and correct regardless of
      # whether NEO4J_HOME/data is currently a real directory (a fresh
      # extraction's own shipped skeleton, replaced here exactly once per
      # distribution download) or a symlink left over from an earlier job
      # that happened to reuse this same compute node.
      rm -rf "$NEO4J_HOME/data"
      ln -s "$NEO4J_JOB_DATA_DIR" "$NEO4J_HOME/data"

      # Same password-persistence reasoning as before, just scoped to this
      # job's own data directory now instead of the old shared-forever
      # one: the password is set into the store itself on first init and
      # must match on every later restart against the same data — within
      # a single job, "later restart" means neo4j getting stopped/started
      # again inside the SAME job, not a different sbatch submission.
      # set-initial-password only works before the store has ever started
      # once, so guard it with our own marker rather than depending on
      # neo4j-admin's own error behavior on a repeat call against an
      # already-initialized store.
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
            # engine/memory/client.py falls back to local Ollama for both the
            # memory LLM and embedder whenever LITELLM_API_KEY isn't set —
            # a required model is already present per the check above
            # (DEEPSEEK_R1_TAG/QWEN3_CODER_TAG/gpt-oss:20b), but
            # nomic-embed-text (the embedder fallback) isn't pulled
            # anywhere else, and unlike those it's small enough (~274MB)
            # to just pull here rather than requiring it to already be
            # present.
            if [ -z "${LITELLM_API_KEY:-}" ]; then
              echo "LITELLM_API_KEY not set — memory layer will use local Ollama; pulling nomic-embed-text..."
              if ! ollama pull nomic-embed-text; then
                echo "'ollama pull nomic-embed-text' failed — memory embedding calls will fail" >&2
                echo "until this model is available (see engine/memory/client.py)." >&2
              fi
            fi
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

# Understand-Anything (a semantic complement to CodeGraph's structural
# index) was removed 2026-09-17: across every attempt on record — several
# distinct failure modes (a silently-denied permission, a hallucinated
# tool name, an unbuilt plugin core, the model ignoring unattended-mode
# instructions) fixed one at a time over several weeks — the graph it
# produces was never once actually read by the norm-implementer, even
# after the instructions were tightened specifically to require it. Real,
# repeated engineering cost for a feature that provably never delivered
# value. See CLAUDE.md's "Understand-Anything" history for the full record
# of what was tried.

# Run through the venv's interpreter, not the container's bare python3 —
# that's the whole point of building it above. engine/simulate.py itself
# and everything it imports besides engine/llm_agents.py and
# engine/monitoring.py (engine/call_log, mechanisms/*, actions/*) is
# stdlib-only, so this venv (litellm/pydantic/python-dotenv/matplotlib,
# no --system-site-packages) has everything the run needs; the opencode
# subprocess call for the norm pipeline agents is an external binary,
# unaffected by which Python interpreter launched it.
# Run as a module (-m engine.simulate), not a script path, so `engine`
# resolves as a package relative to $SLURM_SUBMIT_DIR (the repo root and
# cwd here) — a plain `python3 engine/simulate.py` would put engine/ itself
# on sys.path instead and break every `from engine.x import y` inside it.
"$FISHERY_VENV/bin/python3" -m engine.simulate --max-rounds "${MAX_ROUNDS:-100}"
