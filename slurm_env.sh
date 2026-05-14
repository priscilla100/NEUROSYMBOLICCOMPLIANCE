#!/usr/bin/env bash
# slurm_env.sh — sourced by all SLURM job scripts
# Usage: source slurm/slurm_env.sh
#
# Sets up conda, env vars, PYTHONPATH, and verifies Soufflé is available.

# ── Conda ─────────────────────────────────────────────────────────────────────
unset VIRTUAL_ENV PYTHONPATH
source /home/pdanso/miniconda3/etc/profile.d/conda.sh
conda activate compliance_env

# ── Project root (resolve from this file's location) ─────────────────────────
PROJECT_ROOT="/home/pdanso/COMPLIANCEGPT"
cd "${PROJECT_ROOT}"

# ── HuggingFace credentials ───────────────────────────────────────────────────
set -a; source "${PROJECT_ROOT}/.env"; set +a
export HF_TOKEN="${HUGGINGFACE_API_KEY}"
export HUGGING_FACE_HUB_TOKEN="${HUGGINGFACE_API_KEY}"
export HF_HUB_TOKEN="${HUGGINGFACE_API_KEY}"
export HF_CACHE_DIR="${HF_CACHE_DIR:-/home/pdanso/hf_cache}"

# ── PYTHONPATH — makes `connector`, `app`, `datalog_engine` importable ────────
# batch_runner.py imports from connector/ and app/strategies/
# Without this, `import connector.model_client` fails on the cluster.
export PYTHONPATH="${PROJECT_ROOT}:${PROJECT_ROOT}/app:${PROJECT_ROOT}/connector:${PYTHONPATH:-}"

# ── Soufflé — required for `formal` and `agentic` strategies ─────────────────
# The formal strategy shells out to `souffle` to run .dl files in datalog_engine/
# Check it's on PATH; if not, try conda-installed location.
if ! command -v souffle &>/dev/null; then
    # Try common conda install location
    SOUFFLE_BIN="${HOME}/miniconda3/envs/compliance_env/bin/souffle"
    if [ -f "${SOUFFLE_BIN}" ]; then
        export PATH="$(dirname ${SOUFFLE_BIN}):${PATH}"
        echo "=== Soufflé found at ${SOUFFLE_BIN} ==="
    else
        echo "WARNING: souffle not found on PATH — formal/agentic strategies will fail."
        echo "  Install with: conda install -c conda-forge souffle"
        echo "  Or: sudo apt-get install souffle"
    fi
else
    echo "=== Soufflé: $(which souffle) — $(souffle --version 2>&1 | head -1) ==="
fi

# ── Datalog engine path — so strategies can find .dl files ───────────────────
export DATALOG_ENGINE_DIR="${PROJECT_ROOT}/datalog_engine"

# ── Shared dirs ───────────────────────────────────────────────────────────────
mkdir -p "${PROJECT_ROOT}/logs"
mkdir -p "${PROJECT_ROOT}/results/cluster_run"

# ── Diagnostics (printed by every job) ───────────────────────────────────────
echo "=== Node:       $(hostname) ==="
echo "=== Python:     $(which python) ==="
echo "=== PYTHONPATH: ${PYTHONPATH} ==="
echo "=== HF_TOKEN:   $([ -n "$HF_TOKEN" ] && echo SET || echo MISSING) ==="
echo "=== HF_CACHE:   ${HF_CACHE_DIR} ==="
echo "=== DATALOG:    ${DATALOG_ENGINE_DIR} ==="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "(no nvidia-smi)"
