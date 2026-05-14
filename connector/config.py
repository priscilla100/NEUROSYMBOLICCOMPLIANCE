"""
connector/config.py
─────────────────────────────────────────────────────────────────────────────
Central configuration. Edit DATALOG_ENGINE_DIR to point to your datalog_engine.

All other files import from here — no more hardcoded paths scattered around.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file if it exists
# ── Project root (the COMPLIANCEGPT/ folder) ──────────────────────────────
# This file lives at COMPLIANCEGPT/connector/config.py
# So project root is two levels up.
_THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = _THIS_FILE.parent.parent   # COMPLIANCEGPT/

# ── Souffle datalog engine ─────────────────────────────────────────────────
# Change this if your datalog_engine lives somewhere else.
DATALOG_ENGINE_DIR = str(PROJECT_ROOT / "datalog_engine")

# ── Anthropic API key ──────────────────────────────────────────────────────
# Loaded from environment or .env file. Never hardcode your key here.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Models ─────────────────────────────────────────────────────────────────
# Model selection is controlled by connector/settings.py (Settings.llm1_model / llm1_provider,
# llm2_model / llm2_provider).  Do NOT hardcode models here — they are read from user settings
# at runtime via get_settings() in every strategy and LLM client.
# LLM1_MODEL / LLM2_MODEL were removed to prevent confusion with the settings system.

# ── Souffle binary ─────────────────────────────────────────────────────────
# Set to None to auto-detect. Set to a path if souffle isn't on PATH.
# Example: SOUFFLE_BINARY = "/opt/homebrew/bin/souffle"
SOUFFLE_BINARY = None

# ── Timeouts ───────────────────────────────────────────────────────────────
SOUFFLE_TIMEOUT_SECONDS = 30

# ── Benchmark data ─────────────────────────────────────────────────────────
BENCHMARK_CSV = str(PROJECT_ROOT / "data" / "hipaa_qa_dataset.csv")


def _active_provider() -> str:
    """Return the active LLM1 provider from settings, or empty string if unavailable."""
    try:
        from connector.settings import get_settings
        return get_settings().llm1_provider or ""
    except Exception:
        return ""


def validate() -> list[str]:
    """Return a list of configuration problems (empty = all good)."""
    problems = []
    if not os.path.isdir(DATALOG_ENGINE_DIR):
        problems.append(f"DATALOG_ENGINE_DIR not found: {DATALOG_ENGINE_DIR}")
    # Only warn about missing Anthropic key when provider is actually anthropic
    provider = _active_provider()
    if provider == "anthropic" and not ANTHROPIC_API_KEY:
        problems.append("ANTHROPIC_API_KEY not set. Run: export ANTHROPIC_API_KEY=sk-ant-...")
    required = [
        "hipaa_types.dl", "hipaa_hierarchies.dl", "hipaa_macros.dl",
        "hipaa_stubs.dl", "hipaa_164_502.dl", "hipaa_164_506.dl",
        "hipaa_top.dl", "hipaa_main.dl",
    ]
    for f in required:
        if not os.path.exists(os.path.join(DATALOG_ENGINE_DIR, f)):
            problems.append(f"Missing required file: datalog_engine/{f}")
    return problems


if __name__ == "__main__":
    print(f"PROJECT_ROOT:       {PROJECT_ROOT}")
    print(f"DATALOG_ENGINE_DIR: {DATALOG_ENGINE_DIR}")
    problems = validate()
    if problems:
        print("\n⚠️  Configuration problems:")
        for p in problems:
            print(f"  • {p}")
    else:
        print("\n✓ Configuration looks good.")
