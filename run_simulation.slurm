#!/bin/bash
#
# Runs the fishery simulation against gpt-oss:120b via Ollama, on Aoraki
# (University of Otago HPC). Submit from the repo root: sbatch run_simulation.slurm
#
# One-time setup, before the first submission (not part of this script,
# since it needs an empty directory and only needs doing once):
#   mkdir -p ~/bin && cd ~/bin
#   apptainer run /opt/apptainer_img/ollama_shellenv.sif --copy-execute-files
#   echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
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
export SLURM_SUBMIT_DIR  # so hpc_ollama_entrypoint.sh sees it too, inside the container

# Fail loudly if this node isn't actually giving us GPU access, rather than
# letting ollama-env.sh silently fall back to CPU-only (it does exactly that
# if nvidia-smi isn't found — see the script's own source) and burning the
# whole time allocation running gpt-oss:120b unusably slowly on CPU.
if ! nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi not found/working on this node — GPU wasn't actually allocated" >&2
  echo "or the driver isn't visible. Check your --partition/--gpus-per-node above." >&2
  exit 1
fi

export OLLAMA_MODELS=/projects/sciences/computing/cranefield_lab/magha601/models
export MAX_ROUNDS="${MAX_ROUNDS:-20}"

if ! command -v ollama-env.sh >/dev/null 2>&1; then
  echo "ollama-env.sh not found on PATH — see the one-time setup step in this" >&2
  echo "script's header comment before submitting." >&2
  exit 1
fi

# ollama-env.sh just execs `apptainer run --nv --bind /mnt --bind /projects
# <image> "$@"` — it doesn't export OLLAMA_HOST back to this shell, that only
# exists inside the container the apptainer run starts. So everything that
# needs OLLAMA_HOST (pointing opencode at it, then running the simulation)
# has to happen AS the command we hand to ollama-env.sh, not after it.
ollama-env.sh bash "$SLURM_SUBMIT_DIR/hpc_ollama_entrypoint.sh"
