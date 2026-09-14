#!/bin/bash
#
# Runs the fishery simulation on Aoraki (University of Otago HPC). The
# fisher agent runs on the local Ollama gpt-oss:20b model (FISHER_MODEL);
# the norm-implementer/norm-evaluator (opencode) agents route to
# NORM_IMPLEMENTER_MODEL — back on the local Ollama gpt-oss:120b model as
# of 2026-09-14 (litellm/Kimi-K2.5's quota was exhausted; see CLAUDE.md's
# "Norm-implementer/evaluator back on the local model" entry) — see
# hpc_ollama_entrypoint.sh for where these get set. OPENCODE_MODEL is the
# same local gpt-oss:120b, also used for the optional Understand-Anything
# knowledge-graph build/refresh (BUILD_KNOWLEDGE_GRAPH=1). Submit
# from the repo root: sbatch ops/run_simulation.slurm — this script and
# hpc_ollama_entrypoint.sh both moved into ops/ on 2026-09-14 (operational/
# infra scripts, plus logs/ and plots/, out of the repo root specifically
# so opencode's own read/glob/grep exploration never wastes a tool call on
# them — see CLAUDE.md's "ops/ split" entry). $SLURM_SUBMIT_DIR is still
# wherever `sbatch` itself was invoked from (the repo root), unaffected by
# where this script file itself lives.
#
# Structure follows Otago's own ollama-batch-example.slurm: the container
# takes ONE command string as its argument and runs it via its internal
# bash shell (not separate argv entries) — everything that needs
# OLLAMA_HOST (which only exists inside that container process) has to be
# in hpc_ollama_entrypoint.sh, run as that one string.
#
#SBATCH --job-name=fishery-sim
#SBATCH --partition=aoraki_gpu_H100    # 80GB VRAM per GPU — gpt-oss:120b alone needs most of
                                        #   one card, and it shares whichever GPU it's on with
                                        #   gpt-oss:20b (Ollama swaps between them; see
                                        #   hpc_ollama_entrypoint.sh). Requesting 2 (below) is a
                                        #   real single-node, NVLink-connected pair, not a
                                        #   cross-node request — confirmed directly via `scontrol
                                        #   show node aoraki16`: this partition's nodes
                                        #   (aoraki[16,30]) each have 4 physical H100s
                                        #   (`Gres=gpu:H100:4`) in one chassis; the partition's
                                        #   own "Max GPUs: 2" is a per-job quota, not the node's
                                        #   real capacity. Alternative: aoraki_gpu_A100_80GB.
                                        #   Do NOT use aoraki_gpu_L40 (48GB) or
                                        #   aoraki_gpu_A100_40GB (40GB) — too small.
                                        #   Do NOT use the generic aoraki_gpu pool either —
                                        #   it could land you on an L40/40GB node.
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:2                   # 2 real NVLink-paired H100s on one node (2026-09-14) —
                                        #   was gpu:1; see OLLAMA_SCHED_SPREAD below for what
                                        #   this is actually for.
#SBATCH --cpus-per-task=10             # matches Otago's own example; Aoraki asks for >=2/GPU
#SBATCH --mem=64G                      # CPU RAM, not GPU VRAM (fixed by the partition above) —
                                        #   raised 32G -> 64G (2026-09-14): headroom for the
                                        #   optional Neo4j JVM (ENABLE_NEO4J_MEMORY=1) and the
                                        #   Understand-Anything pnpm/build-agent step
                                        #   (BUILD_KNOWLEDGE_GRAPH=1), neither of which had been
                                        #   directly measured against the old 32G — well under the
                                        #   aoraki_gpu_H100 partition's own 150G/job cap. Still a
                                        #   guess, not measured: run a short test round and check
                                        #   `seff <jobid>` to right-size this for real.
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
# Forces Ollama's own scheduler to spread a model's layers across every
# visible GPU rather than packing it onto as few as possible — the actual
# point of requesting 2 GPUs above (2026-09-14). gpt-oss:120b alone already
# fits on one 80GB card (DCGM measured ~63GB peak at the old 65536-token
# context), so without this Ollama would likely just use one of the two
# GPUs and leave the second idle; this trades that "fits on one" default
# for real headroom (a much bigger num_ctx below, more margin generally)
# by using both. Applies server-wide, not per-model — the 20B fisher model
# will also be eligible for spreading across both GPUs even though it
# doesn't need to, since Ollama has no per-model override for this; harmless
# (just doesn't use the second card's bandwidth for that smaller model),
# just not the surgical "120B only" scoping that would be ideal. Not
# verified against the exact Ollama version baked into ollama_shellenv.sif
# — if unsupported, an unrecognized env var should just be ignored, not
# fail the job, but this hasn't been confirmed on a real run yet.
export OLLAMA_SCHED_SPREAD=1
# Opt-in, off by default — see hpc_ollama_entrypoint.sh for the initial
# build and engine/simulate.py's refresh_knowledge_graph() for the
# per-round follow-up, and why neither is on by default (real extra GPU
# time every time, not free like codegraph). Submit with
# BUILD_KNOWLEDGE_GRAPH=1 sbatch ops/run_simulation.slurm to build a fresh
# Understand-Anything semantic graph before this run starts AND keep it
# incrementally refreshed after every round that commits a norm.
export BUILD_KNOWLEDGE_GRAPH="${BUILD_KNOWLEDGE_GRAPH:-0}"

# Opt-in, off by default — see hpc_ollama_entrypoint.sh for the nested
# Apptainer Neo4j instance this starts and health-checks before exporting
# NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD. Genuinely unverified end-to-end on a
# real Aoraki job (see that script's comments and CLAUDE.md) — every
# failure path there degrades to today's behavior (memory layer off), so
# this is safe to try, just not guaranteed to actually come up. Submit with
# ENABLE_NEO4J_MEMORY=1 sbatch ops/run_simulation.slurm to try it.
export ENABLE_NEO4J_MEMORY="${ENABLE_NEO4J_MEMORY:-0}"

# Direct apptainer invocation, matching the (uncommented, i.e. recommended)
# form in Otago's own ollama-batch-example.slurm — this is what ollama-env.sh
# itself runs internally, so there's no need for the one-time PATH setup
# ollama-env.sh normally requires. One quoted string, run via the container's
# internal shell; not separate argv entries (that's what the earlier version
# of this script got wrong).
IMAGE_PATH="/opt/apptainer_img/ollama_shellenv.sif"

# Expose the host's system JVM into the container too (2026-09-02) — the
# login node has one at /usr/lib/jvm/java-17-openjdk-17.0.20.0.8-1.2.el9_8.x86_64
# (confirmed via `readlink -f $(command -v java)`; JAVA_HOME is unset there,
# so it's a plain OS package via the RHEL alternatives system, not a module
# load — nothing else needs to happen on the submitting shell's side for
# this to work). ollama_shellenv.sif has no JVM of its own at all
# (hpc_ollama_entrypoint.sh's Neo4j setup previously found "no 'java' binary
# reachable inside this container" on a real job), and /usr/lib/jvm wasn't
# bound in before this. This check runs on whatever node actually executes
# this sbatch script (the allocated compute node, not the login node the
# job was submitted from) — if that node's /usr/lib/jvm doesn't exist,
# apptainer just doesn't get the extra --bind, and
# hpc_ollama_entrypoint.sh's own portable-Eclipse-Temurin-JRE download
# (checked first here, before the download) still exists as a fallback
# either way. Whether a GPU compute node actually shares the login node's
# /usr/lib/jvm contents is what this line resolves at runtime rather than
# assumes up front.
APPTAINER_BINDS=(--bind /mnt --bind /projects)
if [ -d /usr/lib/jvm ]; then
  APPTAINER_BINDS+=(--bind /usr/lib/jvm)
  # A real job confirmed the host JVM alone isn't enough: it crashed on
  # every invocation with "Error loading java.security file" /
  # NoClassDefFoundError in sun.security.jca.Providers — the well-known
  # RHEL OpenJDK container gotcha. RHEL's java.security patches in
  # `include /etc/crypto-policies/back-ends/java.config`, and without this
  # directory bound in, the JVM can't resolve that include at all.
  # hpc_ollama_entrypoint.sh's own java-detection now also verifies `java
  # -version` actually succeeds (not just that the binary exists) and
  # falls back to the portable JRE download if not, so this bind is a real
  # fix attempt, not the only safety net — but worth doing directly since
  # the actual cause is now identified, not just worked around.
  if [ -d /etc/crypto-policies ]; then
    APPTAINER_BINDS+=(--bind /etc/crypto-policies)
  fi
fi

apptainer run --nv "${APPTAINER_BINDS[@]}" "$IMAGE_PATH" \
  "bash $SLURM_SUBMIT_DIR/ops/hpc_ollama_entrypoint.sh"
