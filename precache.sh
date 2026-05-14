#!/usr/bin/env bash
# precache.sh — run ONCE on the login node (has internet) before sbatch
#
# Downloads embedding models and tokenizer configs so compute nodes
# (no internet) can load them from HF_CACHE_DIR.
#
# Usage:
#   chmod +x precache.sh
#   ./precache.sh
#
# Only needs to run once. After that, all SLURM jobs load from cache.

set -e

source /home/pdanso/miniconda3/etc/profile.d/conda.sh
conda activate compliance_env

set -a; source /home/pdanso/compliance_agent/.env; set +a
export HF_TOKEN="${HF_API_KEY}"
export HUGGING_FACE_HUB_TOKEN="${HF_API_KEY}"
export HF_CACHE_DIR="${HF_CACHE_DIR:-/home/pdanso/hf_cache}"

echo "=== Pre-caching models for cluster jobs ==="
echo "=== HF_CACHE_DIR: ${HF_CACHE_DIR} ==="
mkdir -p "${HF_CACHE_DIR}"

# ── RAG embedding model ───────────────────────────────────────────────────────
# This is what RAGStrategy.build_index() downloads at runtime.
# Pre-cache it here so compute nodes don't need internet.
echo ""
echo "--- Caching RAG embedding model (sentence-transformers) ---"
python -c "
from sentence_transformers import SentenceTransformer
import os
model = SentenceTransformer('all-MiniLM-L6-v2', cache_folder=os.environ.get('HF_CACHE_DIR'))
print('  all-MiniLM-L6-v2 cached OK')
"

# ── HF instruct models (tokenizer + config only — weights download on first job run) ──
# Downloading tokenizer now means the job doesn't stall on that at init time.
# Full weight download happens automatically on first sbatch run.
echo ""
echo "--- Pre-caching tokenizer configs (fast, no weight download) ---"

python -c "
import os
from transformers import AutoTokenizer

models = [
    # Small tier
    'meta-llama/Llama-3.1-8B-Instruct',
    'mistralai/Mistral-7B-Instruct-v0.3',
    'google/gemma-2-9b-it',
    'Qwen/Qwen2.5-7B-Instruct',
    # Medium tier
    'mistralai/Mistral-Nemo-Instruct-2407',
    'Qwen/Qwen2.5-14B-Instruct',
    # Large tier
    'deepseek-ai/DeepSeek-R1-Distill-Qwen-32B',
    'meta-llama/Llama-3.3-70B-Instruct',
]

token = os.environ.get('HF_TOKEN')
for m in models:
    try:
        tok = AutoTokenizer.from_pretrained(m, token=token, trust_remote_code=True)
        has_template = bool(getattr(tok, 'chat_template', None))
        print(f'  OK  {m}  (chat_template={has_template})')
    except Exception as e:
        print(f'  SKIP {m}: {e}')
"

echo ""
echo "=== Pre-cache complete ==="
echo "=== You can now submit jobs with sbatch ==="
echo ""
echo "Note: model WEIGHTS download on the first job run (compute node"
echo "needs to reach huggingface.co on first run, then loads from cache)."
echo "If your compute nodes have NO internet at all, ask your sysadmin"
echo "to snapshot weights into: ${HF_CACHE_DIR}"
