"""
model_config.py
===============
Single source of truth for LLM model configuration.

Supported providers
-------------------
  anthropic       Claude via Anthropic API
  openai          GPT / o-series via OpenAI API
  google          Gemini via Google Generative AI API
  ollama          Any model running locally via Ollama
  openai_compat   Any OpenAI-compatible endpoint (LM Studio, vLLM, etc.)
  hf              HuggingFace Transformers (local, loaded directly onto GPU)

Model string formats
--------------------
  claude-sonnet-4-20250514                         Anthropic (default when no prefix)
  openai:gpt-4o                                    OpenAI
  openai:gpt-4o-mini
  openai:o3-mini
  google:gemini-2.0-flash                          Google
  google:gemini-2.5-pro
  ollama:llama3.2                                  Local Ollama
  ollama:mistral
  openai-compat:http://host:port:model             Any OpenAI-compatible endpoint
  hf:meta-llama/Llama-3.2-8B-Instruct             HuggingFace local model
  hf:mistralai/Mistral-7B-Instruct-v0.3
  hf:google/gemma-3-4b-it
  hf:google/gemma-3-27b-it
  hf:deepseek-ai/DeepSeek-R1-Distill-Qwen-32B
  hf:Qwen/Qwen2.5-7B-Instruct
  hf:Qwen/Qwen2.5-14B-Instruct

Environment variables
---------------------
  ANTHROPIC_API_KEY
  OPENAI_API_KEY
  GOOGLE_API_KEY
  HF_TOKEN             HuggingFace token (required for gated models: Llama, Gemma)
  HF_CACHE_DIR         Where to cache downloaded models (default: ~/hf_cache)
                       Set this to a path with enough quota (models are 5–70 GB each)
  OLLAMA_BASE_URL      (default: http://localhost:11434)
  COMPLIANCE_MODEL     Override default model
  COMPLIANCE_ROUTER_MODEL
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ── Constants ─────────────────────────────────────────────────────────────────

# Defaults fall back to the connector/settings.py system so the user's UI/CLI model
# selection is respected.  Env vars COMPLIANCE_MODEL / COMPLIANCE_ROUTER_MODEL still
# override everything (used by cluster batch scripts).
def _default_main_model() -> str:
    env = os.environ.get("COMPLIANCE_MODEL", "").strip()
    if env:
        return env
    try:
        from connector.settings import get_settings
        s = get_settings()
        return f"{s['llm1_provider']}/{s['llm1_model']}"
    except Exception:
        return "anthropic/claude-sonnet-4-6"

def _default_router_model() -> str:
    env = os.environ.get("COMPLIANCE_ROUTER_MODEL", "").strip()
    if env:
        return env
    try:
        from connector.settings import get_settings
        s = get_settings()
        return f"{s['llm1_provider']}/{s['llm1_model']}"
    except Exception:
        return "anthropic/claude-haiku-4-5-20251001"

DEFAULT_MAIN_MODEL   = _default_main_model()
DEFAULT_ROUTER_MODEL = _default_router_model()
OLLAMA_BASE_URL      = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# Default HF cache — override with HF_CACHE_DIR env var.
# On the SBU cluster, set HF_CACHE_DIR=~/hf_cache so models land on your
# home quota rather than filling /tmp on the compute node.
HF_CACHE_DIR = os.environ.get(
    "HF_CACHE_DIR",
    os.path.join(os.path.expanduser("~"), "hf_cache"),
)

PROVIDER_LABELS = {
    "anthropic":     "Anthropic",
    "openai":        "OpenAI",
    "google":        "Google",
    "ollama":        "Ollama (local)",
    "openai_compat": "Custom endpoint",
    "hf":            "HuggingFace (local GPU)",
}

# ── HuggingFace model registry ────────────────────────────────────────────────
# Maps the short hf: model IDs to their HuggingFace repo names and metadata.
# gpu_min = minimum number of GPUs recommended on the SBU cluster.
HF_MODELS = [
    # (model_id,                                          label,                          gpu_min)
    ("hf:meta-llama/Llama-3.2-8B-Instruct",              "Llama 3.2 8B  — gated",        1),
    ("hf:mistralai/Mistral-7B-Instruct-v0.3",            "Mistral 7B",                   1),
    ("hf:google/gemma-3-4b-it",                          "Gemma 3 4B    — gated",        1),
    ("hf:google/gemma-3-27b-it",                         "Gemma 3 27B   — gated",        2),
    ("hf:deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",      "DeepSeek-R1 32B",              2),
    ("hf:deepseek-ai/DeepSeek-R1-Distill-Llama-70B",     "DeepSeek-R1 70B",              4),
    ("hf:Qwen/Qwen2.5-7B-Instruct",                      "Qwen 2.5 7B",                  1),
    ("hf:Qwen/Qwen2.5-14B-Instruct",                     "Qwen 2.5 14B",                 1),
    ("hf:Qwen/Qwen2.5-32B-Instruct",                     "Qwen 2.5 32B",                 2),
]

# Known API models shown in the UI picker
ANTHROPIC_MODELS = [
    ("claude-sonnet-4-20250514",  "Claude Sonnet 4   — Best balance of speed/quality"),
    ("claude-opus-4-6",           "Claude Opus 4.6   — Highest quality, slower"),
    ("claude-haiku-4-5-20251001", "Claude Haiku 4.5  — Fastest, cheapest"),
]
OPENAI_MODELS = [
    ("openai:gpt-4o",      "GPT-4o        — OpenAI flagship"),
    ("openai:gpt-4o-mini", "GPT-4o Mini   — Fast and cheap"),
    ("openai:o3-mini",     "o3-mini       — Reasoning model"),
    ("openai:o1",          "o1            — Advanced reasoning"),
]
GOOGLE_MODELS = [
    ("google:gemini-2.0-flash",      "Gemini 2.0 Flash      — Fast multimodal"),
    ("google:gemini-2.5-pro",        "Gemini 2.5 Pro        — Highest quality"),
    ("google:gemini-2.0-flash-lite", "Gemini 2.0 Flash Lite — Ultra fast"),
]


# ── ModelConfig ───────────────────────────────────────────────────────────────

@dataclass
class ModelConfig:
    """
    Describes a single LLM endpoint.

    model_id   : str  — full identifier string (e.g. "hf:meta-llama/Llama-3.2-8B-Instruct")
    provider   : str  — anthropic | openai | google | ollama | openai_compat | hf
    model_name : str  — provider-native name (e.g. "meta-llama/Llama-3.2-8B-Instruct")
    base_url   : str  — for ollama / openai_compat
    api_key    : str  — optional inline key; otherwise read from env
    """
    model_id:   str
    provider:   str
    model_name: str
    base_url:   str = ""
    api_key:    str = ""

    # ── Completion ────────────────────────────────────────────────────────────

    def complete(
        self,
        messages:   List[Dict[str, Any]],
        system:     str = "",
        max_tokens: int = 1000,
        **kwargs,
    ) -> str:
        """Call the model, return response text. Raises on error."""
        fn = {
            "anthropic":     self._anthropic,
            "openai":        self._openai,
            "google":        self._google,
            "ollama":        self._ollama,
            "openai_compat": self._openai_compat,
            "hf":            self._huggingface,
        }.get(self.provider)
        if fn is None:
            raise ValueError(f"Unknown provider: {self.provider!r}")
        return fn(messages, system, max_tokens, **kwargs)

    # ── Provider implementations ──────────────────────────────────────────────

    def _anthropic(self, messages, system, max_tokens, **kw):
        from anthropic import Anthropic
        key = self.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        client = Anthropic(api_key=key) if key else Anthropic()
        safe = {k: v for k, v in kw.items()
                if k in ("temperature", "top_p", "top_k", "stop_sequences")}
        kwargs: Dict[str, Any] = dict(
            model=self.model_name, max_tokens=max_tokens, messages=messages, **safe
        )
        if system:
            kwargs["system"] = system
        return client.messages.create(**kwargs).content[0].text

    def _openai(self, messages, system, max_tokens, **kw):
        try:
            import openai as _oa
        except ImportError:
            raise ImportError("Run: pip install openai")
        key = self.api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise ValueError(
                "OPENAI_API_KEY not set. Get one at https://platform.openai.com/api-keys"
            )
        client = _oa.OpenAI(api_key=key)
        msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
        safe = {k: v for k, v in kw.items()
                if k in ("temperature", "top_p", "stop", "frequency_penalty")}
        resp = client.chat.completions.create(
            model=self.model_name, messages=msgs,
            max_completion_tokens=max_tokens, **safe,
        )
        return resp.choices[0].message.content

    def _google(self, messages, system, max_tokens, **kw):
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("Run: pip install google-generativeai")
        key = self.api_key or os.environ.get("GOOGLE_API_KEY", "")
        if not key:
            raise ValueError(
                "GOOGLE_API_KEY not set. Get one at https://aistudio.google.com/app/apikey"
            )
        genai.configure(api_key=key)
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system or None,
        )
        gc = genai.GenerationConfig(max_output_tokens=max_tokens)
        history = [
            {"role": "user" if m["role"] == "user" else "model",
             "parts": [m["content"]]}
            for m in messages
        ]
        if len(history) > 1:
            chat = model.start_chat(history=history[:-1])
            return chat.send_message(messages[-1]["content"], generation_config=gc).text
        return model.generate_content(messages[-1]["content"], generation_config=gc).text

    def _ollama(self, messages, system, max_tokens, **kw):
        import urllib.request
        msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
        payload = json.dumps({
            "model": self.model_name, "messages": msgs,
            "stream": False, "options": {"num_predict": max_tokens},
        }).encode()
        url = (self.base_url or OLLAMA_BASE_URL).rstrip("/") + "/api/chat"
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())["message"]["content"]

    def _openai_compat(self, messages, system, max_tokens, **kw):
        import urllib.request
        key = self.api_key or os.environ.get("OPENAI_API_KEY", "")
        msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
        payload = json.dumps({
            "model": self.model_name, "messages": msgs, "max_tokens": max_tokens,
        }).encode()
        hdrs = {"Content-Type": "application/json"}
        if key:
            hdrs["Authorization"] = f"Bearer {key}"
        url = self.base_url.rstrip("/") + "/v1/chat/completions"
        req = urllib.request.Request(url, data=payload, headers=hdrs, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]

    def _huggingface(self, messages, system, max_tokens, **kw):
        """
        Load a HuggingFace model directly onto available GPUs and run inference.

        Notes for the SBU cluster
        --------------------------
        - device_map="auto" spreads the model across all GPUs allocated by SLURM.
          Request enough GPUs in your .job file (#SBATCH --gres=gpu:N).
        - torch_dtype=float16 halves VRAM usage vs float32.
        - Models are cached to HF_CACHE_DIR (default ~/hf_cache).
          First run downloads the weights — this can take 10–30 min for large models.
        - Gated models (Llama, Gemma) require HF_TOKEN and accepted terms on HuggingFace.
        """
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
            import torch
        except ImportError:
            raise ImportError(
                "Missing dependencies. Run:\n"
                "  pip install transformers accelerate torch sentencepiece protobuf"
            )

        token    = self.api_key or os.environ.get("HF_TOKEN", "") or None
        cache    = HF_CACHE_DIR

        # ── Build a chat-template-aware prompt ────────────────────────────────
        # Prefer the tokenizer's apply_chat_template if available (most modern
        # instruct models support it). Fall back to a generic format otherwise.
        tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            token=token,
            cache_dir=cache,
        )

        chat_messages = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

        if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
            prompt = tokenizer.apply_chat_template(
                chat_messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        else:
            # Generic fallback format
            parts = []
            if system:
                parts.append(f"<|system|>\n{system}")
            for m in messages:
                tag = "<|user|>" if m["role"] == "user" else "<|assistant|>"
                parts.append(f"{tag}\n{m['content']}")
            parts.append("<|assistant|>")
            prompt = "\n".join(parts)

        # ── Load model ────────────────────────────────────────────────────────
        model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            token=token,
            cache_dir=cache,
            torch_dtype=torch.float16,
            device_map="auto",          # spreads across all SLURM-allocated GPUs
        )

        # ── Run inference ─────────────────────────────────────────────────────
        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=max_tokens,
            do_sample=True,
            temperature=kw.get("temperature", 0.7),
            pad_token_id=tokenizer.eos_token_id,
        )

        result    = pipe(prompt)
        generated = result[0]["generated_text"]

        # Strip the echoed prompt from the output
        if generated.startswith(prompt):
            generated = generated[len(prompt):].strip()

        return generated

    # ── Helpers ───────────────────────────────────────────────────────────────

    def ping(self, timeout: int = 4) -> bool:
        """Quick reachability / key-presence check."""
        try:
            if self.provider == "anthropic":
                return bool(self.api_key or os.environ.get("ANTHROPIC_API_KEY"))
            if self.provider == "openai":
                return bool(self.api_key or os.environ.get("OPENAI_API_KEY"))
            if self.provider == "google":
                return bool(self.api_key or os.environ.get("GOOGLE_API_KEY"))
            if self.provider == "hf":
                # For gated models we need a token; public models always reachable
                return True
            import urllib.request
            base  = self.base_url or OLLAMA_BASE_URL
            probe = base.rstrip("/") + (
                "/api/tags" if self.provider == "ollama" else "/v1/models"
            )
            urllib.request.urlopen(probe, timeout=timeout)
            return True
        except Exception:
            return False

    @property
    def provider_label(self) -> str:
        return PROVIDER_LABELS.get(self.provider, self.provider)

    @property
    def short_name(self) -> str:
        n = self.model_name
        n = re.sub(r"-20\d{6,8}", "", n)
        n = re.sub(r"^claude-", "", n)
        # For HF models, keep just the repo name part (after the org/)
        if "/" in n:
            n = n.split("/")[-1]
        return n

    def __str__(self) -> str:
        return self.model_id

    def __repr__(self) -> str:
        return f"ModelConfig(provider={self.provider!r}, model={self.model_name!r})"


# ── Parser ────────────────────────────────────────────────────────────────────

def get_model(model_id: str, base_url: str = "", api_key: str = "") -> ModelConfig:
    mid = model_id.strip()

    if mid.startswith("openai:"):
        return ModelConfig(model_id=mid, provider="openai",
                           model_name=mid[7:], api_key=api_key)

    if mid.startswith("google:"):
        return ModelConfig(model_id=mid, provider="google",
                           model_name=mid[7:], api_key=api_key)

    if mid.startswith("ollama:"):
        return ModelConfig(model_id=mid, provider="ollama",
                           model_name=mid[7:],
                           base_url=base_url or OLLAMA_BASE_URL)

    if mid.startswith("hf:"):
        return ModelConfig(
            model_id=mid,
            provider="hf",
            model_name=mid[3:],          # e.g. "meta-llama/Llama-3.2-8B-Instruct"
            api_key=api_key,             # or read from HF_TOKEN at call time
        )

    if mid.startswith("openai-compat:"):
        rest = mid[14:]
        m = re.match(r"(https?://.+):([^/:]+)$", rest)
        url, name = (m.group(1), m.group(2)) if m else (rest.rsplit(":", 1) + ["default"])[:2]
        return ModelConfig(model_id=mid, provider="openai_compat",
                           model_name=name, base_url=base_url or url, api_key=api_key)

    # Default → Anthropic
    return ModelConfig(model_id=mid, provider="anthropic",
                       model_name=mid, api_key=api_key)


# ── Resolution ────────────────────────────────────────────────────────────────

def resolve_model(
    explicit: Optional[str] = None,
    env_var: str = "COMPLIANCE_MODEL",
    default: str = DEFAULT_MAIN_MODEL,
) -> ModelConfig:
    if explicit:
        return get_model(explicit)
    env = os.environ.get(env_var, "").strip()
    if env:
        return get_model(env)
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
        with open(p) as f:
            s = json.load(f)
        lst = s.get("models", [])
        val = lst[0] if lst else s.get("model", "")
        if val and val.strip():
            return get_model(val.strip())
    except Exception:
        pass
    return get_model(default)


def resolve_router_model(explicit: Optional[str] = None) -> ModelConfig:
    return resolve_model(explicit, "COMPLIANCE_ROUTER_MODEL", DEFAULT_ROUTER_MODEL)


def resolve_models_list(settings: Optional[dict] = None) -> List[ModelConfig]:
    """Return all configured models; falls back to [default] if none set."""
    if settings is None:
        try:
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
            with open(p) as f:
                settings = json.load(f)
        except Exception:
            settings = {}
    ids: list = settings.get("models", [])
    if not ids:
        return [resolve_model()]
    out = []
    for mid in ids:
        try:
            out.append(get_model(mid.strip()))
        except Exception as e:
            print(f"[model_config] Skipping bad model {mid!r}: {e}")
    return out or [resolve_model()]


# ── Ollama / key utilities ────────────────────────────────────────────────────

def list_ollama_models(base_url: str = OLLAMA_BASE_URL) -> List[str]:
    import urllib.request
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=5) as r:
            return [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:
        return []


def check_ollama_available(base_url: str = OLLAMA_BASE_URL) -> bool:
    import urllib.request
    try:
        urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=3)
        return True
    except Exception:
        return False


def check_api_keys() -> Dict[str, bool]:
    return {
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "openai":    bool(os.environ.get("OPENAI_API_KEY")),
        "google":    bool(os.environ.get("GOOGLE_API_KEY")),
        "hf":        bool(os.environ.get("HF_TOKEN")),
    }


# ── Singletons ────────────────────────────────────────────────────────────────

DEFAULT_MODEL  = resolve_model()
DEFAULT_ROUTER = resolve_router_model()