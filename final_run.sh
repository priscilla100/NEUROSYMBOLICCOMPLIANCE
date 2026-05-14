#!/usr/bin/env bash
# ============================================================
# ComplianceGPT — Final Run (server script)
# Covers everything after the base ablation:
#   1. Missing gpt-oss strategies
#   2. qwen3:14b — all 10 strategies (primary paper model)
#   3. Component evals — 72B models, formal pipeline only
#   4. LLM1 field-level accuracy eval
#   5. LLM2 faithfulness eval
#   6. Model-swap ablation (5 LLM1×LLM2 pairs)
#
# USAGE:  bash final_run.sh
# Run from project root on the vast.ai server.
# No backslash line continuations — all args on one line.
# ============================================================

set -euo pipefail
cd "$(dirname "$0")"

export OLLAMA_KEEP_ALIVE=24h

echo "=================================================="
echo "  ComplianceGPT — Final Run"
echo "  Started: $(date)"
echo "=================================================="

# ── Steps 1-2: Ablation benchmark — ALREADY DONE ────────────
# gpt-oss and qwen3:14b confirmed complete.
# Skipped.

# ── Steps 3-5: Component evals — ALREADY DONE ───────────────
# eval_component1.csv, eval_component2.csv, eval_e2e.csv confirmed present
# Skipped.

# ── Steps 6-7: Large model evals — DEFERRED to new server ───
# evaluate_llm1.py (qwen2.5:72b) and evaluate_llm2.py held for 72B server.
# Skipped.

# ── Step 8: Model-swap ablation (20 cross pairs, LLM1 ≠ LLM2) ──
# Full 5×4 matrix: each of 5 models as LLM1 × each of 4 other models as LLM2
echo ""
echo "── Step 8: Model-swap ablation (20 cross pairs) ─────────"

# ── LLM1 = llama3.2 ─────────────────────────────────────────
echo "   [1/20]  llama3.2 (LLM1) × mistral (LLM2)"
python3 eval_e2e.py --llm1 ollama/llama3.2:latest --llm2 ollama/mistral:latest --out data/eval_e2e_llama32-mistral.csv --skip-existing --delay 3.0 || echo "[WARN] llama32-mistral failed — continuing"

echo "   [2/20]  llama3.2 (LLM1) × gemma:7b (LLM2)"
python3 eval_e2e.py --llm1 ollama/llama3.2:latest --llm2 ollama/gemma:7b --out data/eval_e2e_llama32-gemma7b.csv --skip-existing --delay 3.0 || echo "[WARN] llama32-gemma7b failed — continuing"

echo "   [3/20]  llama3.2 (LLM1) × gpt-oss (LLM2)"
python3 eval_e2e.py --llm1 ollama/llama3.2:latest --llm2 ollama/gpt-oss:latest --out data/eval_e2e_llama32-gptoss.csv --skip-existing --delay 3.0 || echo "[WARN] llama32-gptoss failed — continuing"

echo "   [4/20]  llama3.2 (LLM1) × qwen3:14b (LLM2)"
python3 eval_e2e.py --llm1 ollama/llama3.2:latest --llm2 ollama/qwen3:14b --out data/eval_e2e_llama32-qwen3.csv --skip-existing --delay 3.0 || echo "[WARN] llama32-qwen3 failed — continuing"

# ── LLM1 = mistral ──────────────────────────────────────────
echo "   [5/20]  mistral (LLM1) × llama3.2 (LLM2)"
python3 eval_e2e.py --llm1 ollama/mistral:latest --llm2 ollama/llama3.2:latest --out data/eval_e2e_mistral-llama32.csv --skip-existing --delay 3.0 || echo "[WARN] mistral-llama32 failed — continuing"

echo "   [6/20]  mistral (LLM1) × gemma:7b (LLM2)"
python3 eval_e2e.py --llm1 ollama/mistral:latest --llm2 ollama/gemma:7b --out data/eval_e2e_mistral-gemma7b.csv --skip-existing --delay 3.0 || echo "[WARN] mistral-gemma7b failed — continuing"

echo "   [7/20]  mistral (LLM1) × gpt-oss (LLM2)"
python3 eval_e2e.py --llm1 ollama/mistral:latest --llm2 ollama/gpt-oss:latest --out data/eval_e2e_mistral-gptoss.csv --skip-existing --delay 3.0 || echo "[WARN] mistral-gptoss failed — continuing"

echo "   [8/20]  mistral (LLM1) × qwen3:14b (LLM2)"
python3 eval_e2e.py --llm1 ollama/mistral:latest --llm2 ollama/qwen3:14b --out data/eval_e2e_mistral-qwen3.csv --skip-existing --delay 3.0 || echo "[WARN] mistral-qwen3 failed — continuing"

# ── LLM1 = gemma:7b ─────────────────────────────────────────
echo "   [9/20]  gemma:7b (LLM1) × llama3.2 (LLM2)"
python3 eval_e2e.py --llm1 ollama/gemma:7b --llm2 ollama/llama3.2:latest --out data/eval_e2e_gemma7b-llama32.csv --skip-existing --delay 3.0 || echo "[WARN] gemma7b-llama32 failed — continuing"

echo "   [10/20] gemma:7b (LLM1) × mistral (LLM2)"
python3 eval_e2e.py --llm1 ollama/gemma:7b --llm2 ollama/mistral:latest --out data/eval_e2e_gemma7b-mistral.csv --skip-existing --delay 3.0 || echo "[WARN] gemma7b-mistral failed — continuing"

echo "   [11/20] gemma:7b (LLM1) × gpt-oss (LLM2)"
python3 eval_e2e.py --llm1 ollama/gemma:7b --llm2 ollama/gpt-oss:latest --out data/eval_e2e_gemma7b-gptoss.csv --skip-existing --delay 3.0 || echo "[WARN] gemma7b-gptoss failed — continuing"

echo "   [12/20] gemma:7b (LLM1) × qwen3:14b (LLM2)"
python3 eval_e2e.py --llm1 ollama/gemma:7b --llm2 ollama/qwen3:14b --out data/eval_e2e_gemma7b-qwen3.csv --skip-existing --delay 3.0 || echo "[WARN] gemma7b-qwen3 failed — continuing"

# ── LLM1 = gpt-oss ──────────────────────────────────────────
echo "   [13/20] gpt-oss (LLM1) × llama3.2 (LLM2)"
python3 eval_e2e.py --llm1 ollama/gpt-oss:latest --llm2 ollama/llama3.2:latest --out data/eval_e2e_gptoss-llama32.csv --skip-existing --delay 3.0 || echo "[WARN] gptoss-llama32 failed — continuing"

echo "   [14/20] gpt-oss (LLM1) × mistral (LLM2)"
python3 eval_e2e.py --llm1 ollama/gpt-oss:latest --llm2 ollama/mistral:latest --out data/eval_e2e_gptoss-mistral.csv --skip-existing --delay 3.0 || echo "[WARN] gptoss-mistral failed — continuing"

echo "   [15/20] gpt-oss (LLM1) × gemma:7b (LLM2)"
python3 eval_e2e.py --llm1 ollama/gpt-oss:latest --llm2 ollama/gemma:7b --out data/eval_e2e_gptoss-gemma7b.csv --skip-existing --delay 3.0 || echo "[WARN] gptoss-gemma7b failed — continuing"

echo "   [16/20] gpt-oss (LLM1) × qwen3:14b (LLM2)"
python3 eval_e2e.py --llm1 ollama/gpt-oss:latest --llm2 ollama/qwen3:14b --out data/eval_e2e_gptoss-qwen3.csv --skip-existing --delay 3.0 || echo "[WARN] gptoss-qwen3 failed — continuing"

# ── LLM1 = qwen3:14b ────────────────────────────────────────
echo "   [17/20] qwen3:14b (LLM1) × llama3.2 (LLM2)"
python3 eval_e2e.py --llm1 ollama/qwen3:14b --llm2 ollama/llama3.2:latest --out data/eval_e2e_qwen3-llama32.csv --skip-existing --delay 3.0 || echo "[WARN] qwen3-llama32 failed — continuing"

echo "   [18/20] qwen3:14b (LLM1) × mistral (LLM2)"
python3 eval_e2e.py --llm1 ollama/qwen3:14b --llm2 ollama/mistral:latest --out data/eval_e2e_qwen3-mistral.csv --skip-existing --delay 3.0 || echo "[WARN] qwen3-mistral failed — continuing"

echo "   [19/20] qwen3:14b (LLM1) × gemma:7b (LLM2)"
python3 eval_e2e.py --llm1 ollama/qwen3:14b --llm2 ollama/gemma:7b --out data/eval_e2e_qwen3-gemma7b.csv --skip-existing --delay 3.0 || echo "[WARN] qwen3-gemma7b failed — continuing"

echo "   [20/20] qwen3:14b (LLM1) × gpt-oss (LLM2)"
python3 eval_e2e.py --llm1 ollama/qwen3:14b --llm2 ollama/gpt-oss:latest --out data/eval_e2e_qwen3-gptoss.csv --skip-existing --delay 3.0 || echo "[WARN] qwen3-gptoss failed — continuing"

echo ""
echo "=================================================="
echo "  ALL DONE: $(date)"
echo ""
echo "  Download results:"
echo "    rsync -avz -e 'ssh -p <PORT>' root@<IP>:~/COMPLIANCEGPT/results/ ./results/"
echo "    rsync -avz -e 'ssh -p <PORT>' root@<IP>:~/COMPLIANCEGPT/data/eval_*.csv ./data/"
echo "    rsync -avz -e 'ssh -p <PORT>' root@<IP>:~/COMPLIANCEGPT/evaluate_*.csv ./"
echo "=================================================="
