#!/bin/bash
#
# Runs the fishery simulation against gpt-oss:120b via Ollama, on Aoraki
# (University of Otago HPC). Submit from the repo root: sbatch run_simulation.slurm
#
# One-time setup, before the first submission (not part of this script,
# since it needs an empty directory and only needs doing once):
#   mkdir -p ~/bin && cd ~/bin
#   apptainer run /opt/apptainer_img/ollama_shellenv.sif --copy-execute-files
#   # then make sure ~/bin is on PATH — add to ~/.bashrc if it isn't:
#   echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
#
#SBATCH --job-name=fishery-sim
#SBATCH --partition=aoraki_gpu_H100    # guarantees 80GB VRAM, which gpt-oss:120b needs.
                                        #   Alternative: aoraki_gpu_A100_80GB.
                                        #   Do NOT use aoraki_gpu_L40 (48GB) or
                                        #   aoraki_gpu_A100_40GB (40GB) — too small.
                                        #   Do NOT use the generic aoraki_gpu pool either —
                                        #   it could land you on an L40/40GB node.
#SBATCH --gpus-per-node=1              # --gres=gpu:1 also works but is being deprecated on Aoraki
#SBATCH --cpus-per-task=4              # Aoraki asks for >=2 cores per GPU requested
#SBATCH --mem=32G                      # CPU RAM, not GPU VRAM (that's fixed by the partition
                                        #   choice above) — run a short test round first and
                                        #   check `seff <jobid>` to right-size this for real
#SBATCH --time=08:00:00                # tune from an observed per-round duration x --max-rounds;
                                        #   shorter requests queue faster on Aoraki (backfill)
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.err
# No --account line: Aoraki gives every user a default account per-partition,
# you only need one if you belong to more than one lab group.

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"   # must be the GenerativeSimulation repo root

# ---- Point Ollama at your already-downloaded model weights ----
export OLLAMA_MODELS=/projects/sciences/computing/cranefield_lab/magha601/models

# ---- Start Ollama via Aoraki's Apptainer container ----
if ! command -v ollama-env.sh >/dev/null 2>&1; then
  echo "ollama-env.sh not found on PATH — see the one-time setup step in this" >&2
  echo "script's header comment before submitting." >&2
  exit 1
fi

# NOTE: I haven't been able to test this on Aoraki myself — Otago's docs say
# ollama-env.sh sets OLLAMA_HOST for you but don't show the exact invocation.
# `source` is needed if it's meant to export OLLAMA_HOST into this script's
# shell (most likely, given what it's for). If this doesn't work, run
# `cat "$(command -v ollama-env.sh)"` once to see what it actually does and
# adjust the line below to match.
source ollama-env.sh

if [ -z "${OLLAMA_HOST:-}" ]; then
  echo "OLLAMA_HOST wasn't set after sourcing ollama-env.sh — see the NOTE above." >&2
  exit 1
fi
echo "Ollama running at OLLAMA_HOST=${OLLAMA_HOST}"

echo "Verifying gpt-oss:120b is available (should be instant, already downloaded)..."
ollama list | grep -q "gpt-oss:120b" || ollama pull gpt-oss:120b

# ---- Point opencode's "ollama" provider at THIS job's actual port ----
# opencode.jsonc (committed, shared) has the ollama provider's shape, but a
# fixed default baseURL of 127.0.0.1:11434 — Aoraki's container isolates each
# instance on a different port instead. Override just that, per job, without
# touching the tracked config: .opencode/opencode.json is gitignored and
# opencode merges it in automatically as an extra project-local config layer.
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
        "gpt-oss:120b": { "name": "GPT-OSS 120B (Aoraki Ollama)" }
      }
    }
  }
}
EOF

# ---- opencode itself: plain no-sudo install if this node doesn't have it ----
if ! command -v opencode >/dev/null 2>&1; then
  echo "opencode not on PATH — installing to \$HOME/.opencode"
  curl -fsSL https://opencode.ai/install | bash
  export PATH="$HOME/.opencode/bin:$PATH"
fi

# ---- Run the simulation ----
mkdir -p logs
export OPENCODE_MODEL="ollama/gpt-oss:120b"
python3 simulate.py --max-rounds "${MAX_ROUNDS:-20}"
