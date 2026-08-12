#!/bin/bash
# Runs *inside* ollama-env.sh's apptainer environment — this is the command
# ollama-env.sh execs after starting the ollama server and exporting
# OLLAMA_HOST, not something you run directly. See run_simulation.slurm.
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

echo "Inside the Ollama container environment, OLLAMA_HOST=${OLLAMA_HOST:-<not set>}"
if [ -z "${OLLAMA_HOST:-}" ]; then
  echo "OLLAMA_HOST wasn't set inside the container — ollama-env.sh's behavior" >&2
  echo "may differ from what this script assumes. Check 'cat \$(command -v" >&2
  echo "ollama-env.sh)' and the container's own runscript." >&2
  exit 1
fi

echo "Verifying gpt-oss:120b is available (should be instant, already downloaded)..."
ollama list | grep -q "gpt-oss:120b" || ollama pull gpt-oss:120b

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
        "gpt-oss:120b": { "name": "GPT-OSS 120B (Aoraki Ollama)" }
      }
    }
  }
}
EOF

if ! command -v opencode >/dev/null 2>&1; then
  echo "opencode not on PATH inside the container — installing to \$HOME/.opencode"
  curl -fsSL https://opencode.ai/install | bash
  export PATH="$HOME/.opencode/bin:$PATH"
fi

mkdir -p logs
export OPENCODE_MODEL="ollama/gpt-oss:120b"
python3 simulate.py --max-rounds "${MAX_ROUNDS:-20}"
