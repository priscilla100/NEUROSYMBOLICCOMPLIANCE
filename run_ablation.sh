#!/usr/bin/env bash
# ============================================================
# ComplianceGPT — Full Experiment Runner
# One command runs everything: benchmarks + component evals.
#
# USAGE:  bash run_ablation.sh
#
# REQUIREMENTS:
#   - Ollama running (ollama serve in a separate terminal)
#   - Python 3 + pip install -r requirements.txt
#   - Soufflé installed (brew install souffle-lang/souffle/souffle)
#
# All component evals use Ollama by default (no API key needed).
# To use Claude for component evals:
#   export ANTHROPIC_API_KEY=sk-ant-...
#   LLM1_MODEL=anthropic/claude-sonnet-4-6 bash run_ablation.sh
# ============================================================

set -euo pipefail
cd "$(dirname "$0")"          # always run from project root

# Keep Ollama models loaded for the entire run — prevents costly VRAM eviction
# between strategies for the same model (default is 5 minutes).
export OLLAMA_KEEP_ALIVE=24h

# ── One-command setup ─────────────────────────────────────────
# Installs Python dependencies, checks Soufflé, verifies Ollama,
# and creates default settings if not present.  Safe to re-run.
echo ""; echo "[ setup ] Checking environment…"
bash setup.sh
echo ""

# ── Models to test ───────────────────────────────────────────
# Pull any missing models first:  ollama pull <model>
# Excluded: *-coder (coding-only), all-minilm (embedding-only),
#           qwen3-coder:480b-cloud (remote API), qwen2.5vl (vision).
MODELS=(
    llama3.2:latest   # ~2 GB  — Meta small; shows capability floor for formal pipeline
    mistral:latest    # ~4.4 GB — classic open-source 7B baseline
    gemma:7b          # ~5 GB  — Google Gemma 7B
    gpt-oss:latest    # ~13 GB — GPT-family open source, mid-tier
    qwen3:14b         # ~9.3 GB — strongest available; primary formal pipeline model ★
)
# Total disk: ~34 GB  →  provision ≥60 GB on vast.ai (OS + repo + results overhead)
# All fit on a single RTX 4090 (24 GB VRAM) at ~$0.40/hr
# Estimated runtime: ~14 hrs  →  ~$5.60 well within $10 budget

# ── Best model for component evals (LLM1/LLM2) ───────────────
# LLM1 (extraction): qwen2.5:72b — best structured JSON output for Soufflé mapping
# LLM2 (explanation): llama3.3:70b-instruct-q4_0 — instruction-tuned, fits 48GB VRAM cleanly
# Override at runtime: LLM1_MODEL=ollama/qwen2.5:72b bash run_ablation.sh
COMPONENT_MODEL="${LLM1_MODEL:-ollama/qwen2.5:72b}"
COMPONENT_LLM2_MODEL="${LLM2_MODEL:-ollama/llama3.3:70b-instruct-q4_0}"

# ── Datasets ─────────────────────────────────────────────────
# goldcoin (107 rows, long narrative HIPAA scenarios)
# hipaa_qa  (59 rows, short hand-crafted HIPAA Q&A)
DATASETS="goldcoin hipaa_qa"

# ── Strategies (10 conditions) ───────────────────────────────
# All models run all strategies. Small models (<27B) will error on formal/agentic
# due to LLM1 extraction failures — those errors are logged and reported in the
# paper as evidence of the minimum capability threshold.
STRATEGIES="baseline baseline_fs baseline_cot baseline_fscot
            rag      rag_fs      rag_cot      rag_fscot
            formal   agentic"
# Order rationale: cheap strategies (baseline/RAG) run first per model so partial
# runs still yield usable results if time/budget runs out. formal+agentic last.

echo "=================================================="
echo "  ComplianceGPT Prompt Ablation"
echo "  Datasets:   $DATASETS"
echo "  Strategies: $STRATEGIES"
echo "  Models:     ${MODELS[*]}"
echo "  Started:    $(date)"
echo "=================================================="

python3 run_benchmark.py \
    --models  ${MODELS[@]} \
    --strategies $STRATEGIES \
    --datasets $DATASETS \
    --skip-existing \
    --delay 2.0

echo "=================================================="
echo "  Ollama benchmark DONE: $(date)"
echo "  Results in: results/"
echo "=================================================="

# ── Component Evaluations (Ollama by default; Claude if API key set) ──────────
# Three-component breakdown for the paper:
#   Component 1 — Soufflé engine in isolation (oracle facts → Soufflé verdict)
#   Component 2 — LLM2 faithfulness on Component 1 Soufflé outputs
#   Component 3 — Full end-to-end pipeline (LLM1 → Soufflé → LLM2)
#   + LLM1 field-level accuracy on all 107 GoldCoin rows
#   + LLM2 faithfulness eval on Ollama benchmark results
#
# Model used: $COMPONENT_MODEL (override with LLM1_MODEL / LLM2_MODEL env vars)
# No API key required when using Ollama models.
# =============================================================================

# Resolve per-script args
C1_MODEL_ARG="--model ${COMPONENT_MODEL}"
C2_MODEL_ARG="--model ${COMPONENT_LLM2_MODEL}"
E2E_LLM1_ARG="--llm1 ${COMPONENT_MODEL}"
E2E_LLM2_ARG="--llm2 ${COMPONENT_LLM2_MODEL}"

echo ""
echo "=================================================="
echo "  Component 1: Soufflé engine isolation"
echo "  generate_characteristics → ${COMPONENT_MODEL} (mapping) → Soufflé"
echo "  Output: data/eval_component1.csv"
echo "=================================================="
python3 eval_component1_souffle.py \
    ${C1_MODEL_ARG} \
    --skip-existing \
    --delay 3.0

echo ""
echo "=================================================="
echo "  Component 2: LLM2 explanation faithfulness"
echo "  Soufflé outputs → ${LLM2_MODEL:-${COMPONENT_MODEL}} → rubric scoring"
echo "  Output: data/eval_component2.csv"
echo "=================================================="
python3 eval_component2_llm2.py \
    --component1 data/eval_component1.csv \
    ${C2_MODEL_ARG} \
    --rubric data/explanation_rubric.csv \
    --skip-existing \
    --delay 3.0

echo ""
echo "=================================================="
echo "  Component 3: Full end-to-end pipeline"
echo "  LLM1 → Soufflé → LLM2, 107 rows"
echo "  Output: data/eval_e2e.csv"
echo "=================================================="
python3 eval_e2e.py \
    ${E2E_LLM1_ARG} \
    ${E2E_LLM2_ARG} \
    --skip-existing \
    --delay 3.0

echo ""
echo "=================================================="
echo "  LLM1 field-level accuracy (107 GoldCoin rows)"
echo "  Gold: generate_characteristics keyword mapping"
echo "  Model: ${COMPONENT_MODEL}"
echo "=================================================="
python3 evaluate_llm1.py \
    --goldcoin data/goldcoin.csv \
    --model "${COMPONENT_MODEL}" \
    --out evaluate_llm1_goldcoin_results.csv \
    --delay 3.0

echo ""
echo "=================================================="
echo "  LLM2 faithfulness eval (Ollama benchmark results)"
echo "  Rubric: data/explanation_rubric.csv"
echo "=================================================="
python3 evaluate_llm2.py \
    --results results/ \
    --rubric  data/explanation_rubric.csv \
    --out     evaluate_llm2_results.csv \
    --delay 3.0

echo ""
echo "=================================================="
echo "  ALL EVALS DONE: $(date)"
echo "  Component 1:  data/eval_component1.csv"
echo "  Component 2:  data/eval_component2.csv"
echo "  Component 3:  data/eval_e2e.csv"
echo "  LLM1 eval:    evaluate_llm1_goldcoin_results.csv"
echo "  LLM2 eval:    evaluate_llm2_results.csv"
echo "=================================================="


# ── Model-swap ablation experiments ─────────────────────────────────────────
# Runs Component 3 (eval_e2e.py) with different LLM1/LLM2 combos to test
# interchangeability of extraction and explanation models on the formal pipeline.
# Results written to data/eval_e2e_<tag>.csv for side-by-side comparison.
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "=================================================="
echo "  Model-swap ablation experiments"
echo "  Varying LLM1 (extraction) and LLM2 (explanation)"
echo "=================================================="

# Define experiment matrix: "tag  llm1  llm2"
# Uses advisor's exact Ollama model names.
# Tag format: <llm1_short>-<llm2_short>
declare -a SWAP_EXPERIMENTS=(
    # Same-model pairs — isolate whether LLM1 or LLM2 is the bottleneck
    "llama32-llama32    ollama/llama3.2:latest   ollama/llama3.2:latest"
    "qwen3-qwen3        ollama/qwen3:14b         ollama/qwen3:14b"
    "gptoss-gptoss      ollama/gpt-oss:latest    ollama/gpt-oss:latest"
    # Cross-model: strong extractor (LLM1) + small explainer (LLM2)
    "qwen3-llama32      ollama/qwen3:14b         ollama/llama3.2:latest"
    # Cross-model: small extractor + strong explainer
    "llama32-qwen3      ollama/llama3.2:latest   ollama/qwen3:14b"
)

for ENTRY in "${SWAP_EXPERIMENTS[@]}"; do
    TAG=$(echo "$ENTRY" | awk '{print $1}')
    LLM1=$(echo "$ENTRY" | awk '{print $2}')
    LLM2=$(echo "$ENTRY" | awk '{print $3}')
    OUT="data/eval_e2e_${TAG}.csv"

    echo ""
    echo "── Experiment: $TAG ─────────────────────"
    echo "   LLM1 (extraction):  $LLM1"
    echo "   LLM2 (explanation): $LLM2"
    echo "   Output: $OUT"

    python3 eval_e2e.py \
        --llm1 "$LLM1" \
        --llm2 "$LLM2" \
        --out  "$OUT" \
        --skip-existing \
        --delay 3.0 || echo "  [WARN] $TAG experiment failed — continuing"
done

echo ""
echo "=================================================="
echo "  Model-swap ablation DONE: $(date)"
echo "  Compare outputs with:"
echo "    python3 analyze_results.py --swap-ablation data/eval_e2e_*.csv"
echo "=================================================="
