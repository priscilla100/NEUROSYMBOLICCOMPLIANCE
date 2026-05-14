"""
connector/settings.py
─────────────────────────────────────────────────────────────────────────────
Persistent settings store. Saves to <project_root>/.compliancegpt_settings.json
so settings survive across Streamlit reruns and CLI runs.

Also defines the MODEL_REGISTRY — every supported model across all providers.
"""

import os
import json
from pathlib import Path
from typing import Any

try:
    from connector import config as _config
    _PROJECT_ROOT = Path(_config.DATALOG_ENGINE_DIR).parent
except Exception:
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent

SETTINGS_FILE = _PROJECT_ROOT / ".compliancegpt_settings.json"

# ─────────────────────────────────────────────────────────────────────────────
# Model Registry
# Format: { provider: [ {id, label, context_window, notes, requires} ] }
# ─────────────────────────────────────────────────────────────────────────────

MODEL_REGISTRY = {
    "anthropic": [
        {"id": "claude-opus-4-5",           "label": "Claude Opus 4.5",        "ctx": 200000, "notes": "Most capable"},
        {"id": "claude-sonnet-4-5-20251022", "label": "Claude Sonnet 4.5",      "ctx": 200000, "notes": "Balanced (recommended)"},
        {"id": "claude-haiku-4-5-20251001",  "label": "Claude Haiku 4.5",       "ctx": 200000, "notes": "Fast, low cost"},
        {"id": "claude-opus-4-6",            "label": "Claude Opus 4.6",        "ctx": 200000, "notes": "Latest Opus"},
        {"id": "claude-sonnet-4-6",          "label": "Claude Sonnet 4.6",      "ctx": 200000, "notes": "Latest Sonnet"},
    ],
    "openai": [
        {"id": "gpt-4o",                "label": "GPT-4o",              "ctx": 128000, "notes": "Flagship"},
        {"id": "gpt-4o-mini",           "label": "GPT-4o Mini",         "ctx": 128000, "notes": "Fast, cheap"},
        {"id": "gpt-4-turbo",           "label": "GPT-4 Turbo",         "ctx": 128000, "notes": ""},
        {"id": "o1",                    "label": "o1",                  "ctx": 128000, "notes": "Reasoning"},
        {"id": "o3-mini",               "label": "o3-mini",             "ctx": 128000, "notes": "Fast reasoning"},
    ],
    "google": [
        {"id": "gemini-2.0-flash",          "label": "Gemini 2.0 Flash",        "ctx": 1000000, "notes": "Fast, large ctx"},
        {"id": "gemini-2.0-pro-exp",        "label": "Gemini 2.0 Pro Exp",      "ctx": 1000000, "notes": "Most capable Gemini"},
        {"id": "gemini-1.5-pro",            "label": "Gemini 1.5 Pro",          "ctx": 1000000, "notes": ""},
        {"id": "gemini-1.5-flash",          "label": "Gemini 1.5 Flash",        "ctx": 1000000, "notes": ""},
    ],
    "ollama": [
        {"id": "llama3.3",              "label": "Llama 3.3 70B",       "ctx": 128000, "notes": "Meta, local"},
        {"id": "llama3.2",              "label": "Llama 3.2 3B",        "ctx": 128000, "notes": "Small, fast"},
        {"id": "llama2",                "label": "Llama 2 (latest)",    "ctx": 4096,   "notes": "Legacy 4K ctx — Baseline/RAG only"},
        {"id": "llama2:7b",             "label": "Llama 2 7B",          "ctx": 4096,   "notes": "Legacy 4K ctx — Baseline/RAG only"},
        {"id": "llama2:13b",            "label": "Llama 2 13B",         "ctx": 4096,   "notes": "Legacy 4K ctx — Baseline/RAG only"},
        {"id": "mistral",               "label": "Mistral 7B",          "ctx": 32000,  "notes": "Local"},
        {"id": "mixtral",               "label": "Mixtral 8x7B",        "ctx": 32000,  "notes": "MoE, local"},
        {"id": "deepseek-r1",           "label": "DeepSeek R1",         "ctx": 64000,  "notes": "Reasoning, local"},
        {"id": "qwen2.5",               "label": "Qwen 2.5 72B",        "ctx": 128000, "notes": "Local"},
        {"id": "phi4",                  "label": "Phi-4 14B",           "ctx": 16000,  "notes": "Microsoft, local"},
        {"id": "gemma3",                "label": "Gemma 3 12B",         "ctx": 128000, "notes": "Google, local"},
    ],
    "huggingface": [
        {"id": "meta-llama/Llama-3.3-70B-Instruct",     "label": "Llama 3.3 70B Instruct",  "ctx": 128000, "notes": "HF Inference API"},
        {"id": "mistralai/Mistral-7B-Instruct-v0.3",    "label": "Mistral 7B Instruct",     "ctx": 32000,  "notes": "HF Inference API"},
        {"id": "google/gemma-2-9b-it",                  "label": "Gemma 2 9B IT",           "ctx": 8000,   "notes": "HF Inference API"},
        {"id": "Qwen/Qwen2.5-72B-Instruct",             "label": "Qwen 2.5 72B Instruct",   "ctx": 128000, "notes": "HF Inference API"},
        {"id": "deepseek-ai/DeepSeek-R1",               "label": "DeepSeek R1",             "ctx": 64000,  "notes": "HF Inference API"},
    ],
}

# All model IDs flat (for validation)
ALL_MODEL_IDS = {m["id"] for models in MODEL_REGISTRY.values() for m in models}

# ─────────────────────────────────────────────────────────────────────────────
# Default settings
# ─────────────────────────────────────────────────────────────────────────────

DEFAULTS = {
    # API Keys (prefer env vars; these are overrides)
    "anthropic_api_key":    "",
    "openai_api_key":       "",
    "google_api_key":       "",
    "huggingface_api_key":  "",

    # Model selections per role — default to local Ollama (no API charges)
    "llm1_provider":    "ollama",
    "llm1_model":       "qwen3:14b",
    "llm2_provider":    "ollama",
    "llm2_model":       "qwen3:14b",

    # Ollama
    "ollama_base_url":  "http://localhost:11434",
    "ollama_custom_model": "",          # user can type any model name

    # HuggingFace
    "hf_custom_model":  "",            # user can type any HF model path
    "hf_inference_url": "https://api-inference.huggingface.co",

    # Souffle
    "souffle_binary":   "",            # empty = auto-detect
    "souffle_timeout":  30,

    # RAG
    "rag_k":            5,
    "rag_alpha":        0.5,

    # Active regulation (default HIPAA; others are stubs)
    "active_regulation":    "hipaa",

    # Active strategies for the checker page (persisted from settings)
    "active_strategies":    ["formal"],   # list of: baseline, rag, formal, agentic

    # Active Ollama models (list of model names user has pulled)
    "active_ollama_models": [],

    # Active HuggingFace models (list of model ids)
    "active_hf_models":     [],

    # Batch eval
    "batch_strategy":       "formal",   # baseline | rag | formal | agentic
    "batch_concurrency":    1,          # parallel workers (1 = sequential)
    "batch_question_col":   "question",
    "batch_answer_col":     "answer",
}


# ─────────────────────────────────────────────────────────────────────────────
# Settings store
# ─────────────────────────────────────────────────────────────────────────────

class Settings:
    """
    Persistent key-value settings store backed by a JSON file.
    Merges with DEFAULTS so new keys are always present.

    Usage:
        s = Settings()
        s["llm1_model"] = "gpt-4o"
        model = s["llm1_model"]
        s.save()
    """

    def __init__(self):
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self):
        if SETTINGS_FILE.exists():
            try:
                saved = json.loads(SETTINGS_FILE.read_text())
                self._data.update({k: v for k, v in saved.items() if k in DEFAULTS})
            except Exception:
                pass
        # Layer env vars on top (env vars win over saved file for API keys)
        env_map = {
            "ANTHROPIC_API_KEY":   "anthropic_api_key",
            "OPENAI_API_KEY":      "openai_api_key",
            "GOOGLE_API_KEY":      "google_api_key",
            "HUGGINGFACE_API_KEY": "huggingface_api_key",
        }
        for env_key, setting_key in env_map.items():
            val = os.environ.get(env_key, "")
            if val:
                self._data[setting_key] = val

    def save(self):
        """Write current settings to disk."""
        # Don't save keys that came from env vars (keep them env-only)
        to_save = {k: v for k, v in self._data.items()}
        SETTINGS_FILE.write_text(json.dumps(to_save, indent=2))

    def __getitem__(self, key: str) -> Any:
        return self._data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key: str, value: Any):
        self._data[key] = value

    def get(self, key: str, default=None) -> Any:
        return self._data.get(key, default if default is not None else DEFAULTS.get(key))

    def as_dict(self) -> dict:
        return dict(self._data)

    def get_api_key(self, provider: str) -> str:
        """Get API key for a provider, preferring env vars."""
        env_map = {
            "anthropic":   "ANTHROPIC_API_KEY",
            "openai":      "OPENAI_API_KEY",
            "google":      "GOOGLE_API_KEY",
            "huggingface": "HUGGINGFACE_API_KEY",
        }
        # Env var first
        env_key = env_map.get(provider, "")
        if env_key:
            val = os.environ.get(env_key, "")
            if val:
                return val
        # Then saved setting
        return self._data.get(f"{provider}_api_key", "")

    def get_model_label(self, provider: str, model_id: str) -> str:
        for m in MODEL_REGISTRY.get(provider, []):
            if m["id"] == model_id:
                return m["label"]
        return model_id

    def effective_llm1_model(self) -> tuple[str, str]:
        """Returns (provider, model_id) for LLM1."""
        return self["llm1_provider"], self["llm1_model"]

    def effective_llm2_model(self) -> tuple[str, str]:
        """Returns (provider, model_id) for LLM2."""
        return self["llm2_provider"], self["llm2_model"]


# Singleton — import this everywhere
_instance: Settings | None = None

def get_settings() -> Settings:
    global _instance
    if _instance is None:
        _instance = Settings()
    return _instance
