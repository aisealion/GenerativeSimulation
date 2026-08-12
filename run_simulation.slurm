#!/bin/bash
#
# Runs the fishery simulation against a local Ollama instance (gpt-oss:120b)
# on one GPU node. Submit from the repo root: sbatch run_simulation.slurm
#
# ============================ ADJUST FOR YOUR CLUSTER ============================
# Every #SBATCH line below is a guess at common syntax, not your cluster's actual
# config — check `sinfo`, `sacctmgr show associations user=$USER`, or your HPC
# docs/support desk for the real partition name, GPU resource string, and whether
# an --account/--qos is required before submitting.
#SBATCH --job-name=fishery-sim
#SBATCH --partition=gpu                # ADJUST: your cluster's GPU partition name
#SBATCH --gres=gpu:1                   # ADJUST: e.g. gpu:a100:1 / gpu:h100:1 — needs an
                                        #   80GB-class card (see memory note below);
                                        #   run `sinfo -o "%P %G %m"` to see what's on offer
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=24:00:00                # ADJUST: LLM latency x number of rounds is unpredictable —
                                        #   pad generously, a killed job loses no data (see README)
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.err
# #SBATCH --account=your_project_code  # UNCOMMENT + ADJUST if your cluster requires one
# ===================================================================================

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"   # must be the GenerativeSimulation repo root
mkdir -p logs

# ---- Modules (ADJUST if python3 isn't already on PATH on your cluster) ----
# module load python/3.11

# ---- Ollama: model weights need ~65GB disk — point at scratch, not home quota ----
# ADJUST: replace with your cluster's actual scratch path convention.
export OLLAMA_MODELS="${OLLAMA_MODELS:-$HOME/ollama-models}"
mkdir -p "$OLLAMA_MODELS"

if ! command -v ollama >/dev/null 2>&1; then
  echo "ollama not on PATH — installing a user-local copy (no sudo) to \$HOME/.local"
  curl -fsSL https://ollama.com/install.sh | OLLAMA_INSTALL_DIR="$HOME/.local" sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "Starting ollama server..."
ollama serve > "logs/ollama-${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!
trap 'kill $OLLAMA_PID 2>/dev/null || true' EXIT

echo "Waiting for ollama to come up..."
for i in $(seq 1 30); do
  curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
  sleep 2
done

echo "Pulling gpt-oss:120b (no-op if already cached in \$OLLAMA_MODELS — see the
'pre-pull on a login node' note below if this compute node has no internet access)..."
ollama pull gpt-oss:120b

# ---- opencode: same no-sudo install pattern ----
if ! command -v opencode >/dev/null 2>&1; then
  echo "opencode not on PATH — installing to \$HOME/.opencode"
  curl -fsSL https://opencode.ai/install | bash
  export PATH="$HOME/.opencode/bin:$PATH"
fi

# ---- Run the simulation against the local Ollama model ----
export OPENCODE_MODEL="ollama/gpt-oss:120b"
python3 simulate.py --max-rounds "${MAX_ROUNDS:-20}"
