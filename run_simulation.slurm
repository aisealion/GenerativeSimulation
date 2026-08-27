#!/bin/bash
#
# Runs the fishery simulation on Aoraki (University of Otago HPC). The
# fisher agent runs on the local Ollama gpt-oss:20b model (FISHER_MODEL);
# the norm-implementer (opencode) agent now runs on litellm/Kimi-K2.5 over
# the Otago LiteLLM proxy (NORM_IMPLEMENTER_MODEL), not a local model — see
# hpc_ollama_entrypoint.sh for where those get set, and its LITELLM_API_KEY
# check right above them (must be in this job's environment; sbatch
# propagates the submitting shell's env by default). The local Ollama
# gpt-oss:120b model (OPENCODE_MODEL) is still built and used, but only for
# the optional Understand-Anything knowledge-graph build/refresh
# (BUILD_KNOWLEDGE_GRAPH=1) — not for the norm-implementer anymore. Submit
# from the repo root: sbatch run_simulation.slurm
#
# Structure follows Otago's own ollama-batch-example.slurm: the container
# takes ONE command string as its argument and runs it via its internal
# bash shell (not separate argv entries) — everything that needs
# OLLAMA_HOST (which only exists inside that container process) has to be
# in hpc_ollama_entrypoint.sh, run as that one string.
#
#SBATCH --job-name=fishery-sim
#SBATCH --partition=aoraki_gpu_H100    # guarantees 80GB VRAM — gpt-oss:120b alone needs most
                                        #   of that, and it shares the GPU with gpt-oss:20b
                                        #   (Ollama swaps between them; see hpc_ollama_entrypoint.sh).
                                        #   Alternative: aoraki_gpu_A100_80GB.
                                        #   Do NOT use aoraki_gpu_L40 (48GB) or
                                        #   aoraki_gpu_A100_40GB (40GB) — too small.
                                        #   Do NOT use the generic aoraki_gpu pool either —
                                        #   it could land you on an L40/40GB node.
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1                   # matches Otago's own ollama-batch-example.slurm
#SBATCH --cpus-per-task=10             # matches Otago's own example; Aoraki asks for >=2/GPU
#SBATCH --mem=32G                      # CPU RAM, not GPU VRAM (fixed by the partition above) —
                                        #   run a short test round first and check `seff
                                        #   <jobid>` to right-size this for real
#SBATCH --time=16:00:00                # tune from an observed per-round duration x --max-rounds;
                                        #   shorter requests queue faster on Aoraki (backfill) —
                                        #   if this exceeds the partition's own MaxTime, sbatch
                                        #   rejects the submission outright, so check that if so.
                                        #   Add real margin if submitting with BUILD_KNOWLEDGE_GRAPH=1
                                        #   (below): +30min for the one-time initial build, PLUS up to
                                        #   +10min for EVERY round that actually commits a norm (engine/
                                        #   simulate.py's refresh_knowledge_graph() runs after each one) —
                                        #   for a long run with many adopted norms this can dominate total
                                        #   wall time, not just pad it; size --max-rounds accordingly.
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.err
# No --account line: Aoraki gives every user a default account per-partition,
# you only need one if you belong to more than one lab group.

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"   # must be the GenerativeSimulation repo root
export SLURM_SUBMIT_DIR  # so hpc_ollama_entrypoint.sh sees it too, inside the container

# Fail loudly if this node isn't actually giving us GPU access, rather than
# discovering it 40 minutes into a job that's silently crawling on CPU —
# ollama-env.sh (and the direct apptainer invocation below, which mirrors
# it) both skip --nv and fall back to CPU-only if nvidia-smi isn't found.
if ! nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi not found/working on this node — GPU wasn't actually allocated" >&2
  echo "or the driver isn't visible. Check your --partition/--gres above." >&2
  exit 1
fi

export OLLAMA_MODELS=/projects/sciences/computing/cranefield_lab/magha601/models
export MAX_ROUNDS="${MAX_ROUNDS:-100}"
# Opt-in, off by default — see hpc_ollama_entrypoint.sh for the initial
# build and engine/simulate.py's refresh_knowledge_graph() for the
# per-round follow-up, and why neither is on by default (real extra GPU
# time every time, not free like codegraph). Submit with
# BUILD_KNOWLEDGE_GRAPH=1 sbatch run_simulation.slurm to build a fresh
# Understand-Anything semantic graph before this run starts AND keep it
# incrementally refreshed after every round that commits a norm.
export BUILD_KNOWLEDGE_GRAPH="${BUILD_KNOWLEDGE_GRAPH:-0}"

# Opt-in, off by default — see hpc_ollama_entrypoint.sh for the nested
# Apptainer Neo4j instance this starts and health-checks before exporting
# NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD. Genuinely unverified end-to-end on a
# real Aoraki job (see that script's comments and CLAUDE.md) — every
# failure path there degrades to today's behavior (memory layer off), so
# this is safe to try, just not guaranteed to actually come up. Submit with
# ENABLE_NEO4J_MEMORY=1 sbatch run_simulation.slurm to try it.
export ENABLE_NEO4J_MEMORY="${ENABLE_NEO4J_MEMORY:-0}"

# Direct apptainer invocation, matching the (uncommented, i.e. recommended)
# form in Otago's own ollama-batch-example.slurm — this is what ollama-env.sh
# itself runs internally, so there's no need for the one-time PATH setup
# ollama-env.sh normally requires. One quoted string, run via the container's
# internal shell; not separate argv entries (that's what the earlier version
# of this script got wrong).
IMAGE_PATH="/opt/apptainer_img/ollama_shellenv.sif"
apptainer run --nv --bind /mnt --bind /projects "$IMAGE_PATH" \
  "bash $SLURM_SUBMIT_DIR/hpc_ollama_entrypoint.sh"
