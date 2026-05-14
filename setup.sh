#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
# ComplianceGPT — End-to-End Setup
#
# Prepares the system for artifact evaluation from scratch.
# No environment variables, no manual activation required.
#
# USAGE:  bash setup.sh
#         bash setup.sh --check        # diagnose only, no changes
#         bash setup.sh --pull-models  # also pull all Ollama models
# ══════════════════════════════════════════════════════════════════

set -euo pipefail
cd "$(dirname "$0")"

CHECK_ONLY=false
PULL_MODELS=false
for arg in "$@"; do
    [[ "$arg" == "--check"       ]] && CHECK_ONLY=true
    [[ "$arg" == "--pull-models" ]] && PULL_MODELS=true
done

RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[1;33m'
BLU='\033[0;34m'; BOLD='\033[1m';   NC='\033[0m'

ok()   { echo -e "  ${GRN}✓${NC}  $*"; }
warn() { echo -e "  ${YEL}⚠${NC}  $*"; }
fail() { echo -e "  ${RED}✗${NC}  $*"; }
info() { echo -e "  ${BLU}→${NC}  $*"; }

echo -e "\n${BOLD}ComplianceGPT Setup${NC}"
echo -e "${BOLD}══════════════════════════════════════════${NC}\n"

ERRORS=0

# ── 1. Python version ─────────────────────────────────────────────
echo -e "${BOLD}[1/5] Python${NC}"
if command -v python3 &>/dev/null; then
    PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
        ok "Python $PYVER"
    else
        warn "Python $PYVER — recommend 3.10+"
    fi
else
    fail "python3 not found"; ((ERRORS++))
fi

# ── 2. Python dependencies ────────────────────────────────────────
echo -e "\n${BOLD}[2/5] Python dependencies${NC}"
if $CHECK_ONLY; then
    python3 -c "import rank_bm25, sentence_transformers, anthropic" 2>/dev/null \
        && ok "Core packages installed" \
        || warn "Some packages may be missing (run without --check to install)"
else
    info "Running: pip install -r requirements.txt"
    pip install -r requirements.txt -q && ok "All packages installed" \
        || { fail "pip install failed"; ((ERRORS++)); }
fi

# ── 3. Soufflé Datalog engine ─────────────────────────────────────
echo -e "\n${BOLD}[3/5] Soufflé (formal strategy)${NC}"
if command -v souffle &>/dev/null; then
    SOUFFLE_VER=$(souffle --version 2>&1 | head -1)
    ok "$SOUFFLE_VER"
else
    warn "Soufflé not found — formal/agentic strategies will fail"
    if ! $CHECK_ONLY; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            info "Installing via Homebrew…"
            brew install souffle-lang/souffle/souffle \
                && ok "Soufflé installed" \
                || { fail "brew install failed — install manually: https://souffle-lang.github.io/install"; ((ERRORS++)); }
        elif command -v apt-get &>/dev/null; then
            info "Installing via apt…"
            sudo apt-get install -y souffle \
                && ok "Soufflé installed" \
                || { fail "apt install failed"; ((ERRORS++)); }
        else
            fail "Cannot auto-install on this OS — see https://souffle-lang.github.io/install"
            ((ERRORS++))
        fi
    fi
fi

# ── 4. Ollama ─────────────────────────────────────────────────────
echo -e "\n${BOLD}[4/5] Ollama${NC}"
if command -v ollama &>/dev/null; then
    ok "Ollama binary found: $(which ollama)"
    # Check if server is reachable
    if curl -sf http://localhost:11434/api/tags &>/dev/null; then
        ok "Ollama server is running"
        # List installed models
        INSTALLED=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}' | tr '\n' ' ')
        if [[ -n "$INSTALLED" ]]; then
            ok "Models installed: $INSTALLED"
        else
            warn "No models installed — run: ollama pull llama3.2:latest"
        fi
    else
        warn "Ollama server not running — start it with: ollama serve"
        info "  (leave running in a separate terminal before running benchmarks)"
    fi

    # Optionally pull all models
    if $PULL_MODELS && ! $CHECK_ONLY; then
        echo ""
        info "Pulling all benchmark models (this may take a long time)…"
        MODELS=(
            llama3.2:latest
            mistral:latest
            phi4:latest
            gemma:7b
            gpt-oss:latest
            qwen3:14b
            deepseek-r1:70b
            llama3.1:70b
            llama3.3:70b
            llama3.3:70b-instruct-q4_0
            qwen2.5:72b
            command-r-plus:latest
        )
        for m in "${MODELS[@]}"; do
            if ollama list 2>/dev/null | grep -q "^$m"; then
                ok "Already installed: $m"
            else
                info "Pulling $m …"
                ollama pull "$m" && ok "Pulled: $m" || warn "Failed to pull: $m"
            fi
        done
    fi
else
    fail "Ollama not found — install from https://ollama.com"
    ((ERRORS++))
fi

# ── 5. Settings / .env ────────────────────────────────────────────
echo -e "\n${BOLD}[5/5] Settings${NC}"
SETTINGS_FILE=".compliancegpt_settings.json"
if [[ -f "$SETTINGS_FILE" ]]; then
    ok "Settings file: $SETTINGS_FILE"
else
    if ! $CHECK_ONLY; then
        info "Creating default settings (Ollama / llama3.2:latest)"
        python3 - <<'PYEOF'
import json, pathlib
defaults = {
    "llm1_provider": "ollama",
    "llm1_model":    "llama3.2:latest",
    "llm2_provider": "ollama",
    "llm2_model":    "llama3.2:latest",
    "active_regulation": "hipaa",
    "ollama_base_url":   "http://localhost:11434",
}
pathlib.Path(".compliancegpt_settings.json").write_text(json.dumps(defaults, indent=2))
print("  Written .compliancegpt_settings.json")
PYEOF
        ok "Default settings created"
    else
        warn "Settings file not found — will be auto-created on first run"
    fi
fi

# ── Summary ───────────────────────────────────────────────────────
echo -e "\n${BOLD}══════════════════════════════════════════${NC}"
if [[ $ERRORS -eq 0 ]]; then
    echo -e "${GRN}${BOLD}Setup complete — system ready!${NC}\n"
    echo -e "  Run the full benchmark:   ${BLU}bash run_ablation.sh${NC}"
    echo -e "  Single question (CLI):    ${BLU}python app/cli.py -q \"Can a hospital share records with police?\"${NC}"
    echo -e "  Analyze results:          ${BLU}python analyze_results.py${NC}"
else
    echo -e "${RED}${BOLD}Setup finished with $ERRORS error(s) — fix above before running.${NC}"
fi
echo ""
