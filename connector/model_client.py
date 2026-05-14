"""
connector/model_client.py
─────────────────────────────────────────────────────────────────────────────
Unified LLM client. Routes to Anthropic, OpenAI, Google Gemini, Ollama,
or HuggingFace based on provider name.

Usage:
    client = ModelClient(provider="anthropic", model="claude-sonnet-4-6")
    response = client.complete(system="You are ...", user="Question here")
    # returns plain text string

All providers expose the same .complete(system, user, max_tokens) interface.

HuggingFace local ("hf" provider):
    - Model is loaded ONCE and cached in a module-level dict.
    - Subsequent calls reuse the same model/tokenizer — no reload per row.
    - Supports apply_chat_template for all modern instruct models.
    - Built-in per-call delay to avoid SLURM job timeout from GPU thrashing.
"""

from __future__ import annotations
import os
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from connector.settings import get_settings
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from connector.settings import get_settings


# ── Module-level model cache ──────────────────────────────────────────────────
# Keyed by model name. Holds {"model": ..., "tokenizer": ..., "device": ...}
# This is the fix for the core bug: _huggingface_local was reloading the model
# from disk on every single .complete() call, causing OOM and extreme slowness.
_HF_MODEL_CACHE: dict[str, dict] = {}


# ── Ollama model-specific configuration ───────────────────────────────────────
# True context window limits for Ollama-served models.
# Ollama silently ignores num_ctx values larger than the model's trained limit,
# so we set it correctly to avoid silent truncation of long prompts.
_OLLAMA_CTX: dict[str, int] = {
    "llama2": 4096, "llama2:7b": 4096, "llama2:13b": 4096,
    "llama3": 8192, "llama3.1": 8192, "llama3.2": 131072, "llama3.3": 131072,
    "mistral": 32768, "mixtral": 32768,
    "deepseek-r1": 65536,
    "gemma": 8192, "gemma3": 131072,
    "qwen2.5": 131072, "qwen3": 32768, "phi4": 16384,
    "command-r": 131072, "gpt-oss": 32768,
}

# Reasoning / chain-of-thought models need a longer Ollama request timeout
# because they spend significant time in internal thinking before responding.
_REASONING_KEYWORDS = ("deepseek-r1", "qwq", "o1")

# Models that support a "think" toggle — set think:false to skip reasoning mode
# so that LLM1 extraction (which needs structured JSON output) doesn't time out.
_OLLAMA_THINKING_MODELS = ("qwen3",)


def _ctx_for_ollama_model(model: str) -> int:
    """Return the correct num_ctx to send for an Ollama model tag."""
    m = model.lower()
    for key, ctx in _OLLAMA_CTX.items():
        if key in m:
            return ctx
    return 32768


def _timeout_for_ollama_model(model: str) -> int:
    """Return a per-request timeout (seconds) appropriate for the model."""
    m = model.lower()
    if any(kw in m for kw in _REASONING_KEYWORDS):
        return 360   # deepseek-r1 / qwq think before answering
    if any(kw in m for kw in _OLLAMA_THINKING_MODELS):
        return 480   # qwen3 thinking models: longer budget for reasoning + response
    if any(kw in m for kw in ("70b", "72b", "command-r-plus", "32b", "27b")):
        return 240   # large models are slower
    if any(kw in m for kw in ("gpt-oss", "phi4", "14b", "13b")):
        return 180   # mid-size models need more time on complex CoT/agentic prompts
    return 120


# ── Per-tier inter-call delays (seconds) ─────────────────────────────────────
# These give the GPU time to breathe between rows and prevent the job from
# hitting SLURM's walltime due to memory thrashing or thermal throttling.
# Tune these if your cluster's GPUs are faster/slower.
_HF_DELAY_BY_TIER = {
    "small":  2.0,   # 7–9B  — 1× RTX8000,  fast enough to need a breather
    "medium": 4.0,   # 13–14B — 2× RTX8000
    "large":  8.0,   # 32–70B — 4× RTX8000,  generation is slow, delay prevents overlap
}

# Infer tier from model name so callers don't need to pass it explicitly
def _infer_tier(model_name: str) -> str:
    name = model_name.lower()
    # Large: 32B, 70B, 72B, mixtral (47B effective)
    if any(x in name for x in ["32b", "70b", "72b", "mixtral"]):
        return "large"
    # Medium: 12B, 13B, 14B
    if any(x in name for x in ["12b", "13b", "14b", "nemo"]):
        return "medium"
    # Small: 7B, 8B, 9B, anything else
    return "small"


class ModelClient:
    """
    Unified client for all supported LLM providers.

    Parameters
    ----------
    provider : str
        One of: anthropic | openai | google | ollama | huggingface | hf
    model : str
        Model ID (from MODEL_REGISTRY or custom string for Ollama/HF)
    api_key : str, optional
        Override API key (falls back to settings → env vars)
    base_url : str, optional
        Override base URL (for Ollama custom endpoints)
    hf_delay : float, optional
        Override the auto-detected inter-call delay for HF local inference.
        Pass 0.0 to disable. Default: auto from model name tier.
    """

    SUPPORTED = {"anthropic", "openai", "google", "ollama", "huggingface", "hf"}

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        hf_delay: Optional[float] = None,
    ):
        if provider not in self.SUPPORTED:
            raise ValueError(f"Unknown provider '{provider}'. Supported: {self.SUPPORTED}")
        self.provider = provider
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self._settings = get_settings()

        # Delay between HF local calls — auto-detected from model size tier
        # unless the caller explicitly overrides it.
        if hf_delay is not None:
            self._hf_delay = hf_delay
        else:
            tier = _infer_tier(model)
            self._hf_delay = _HF_DELAY_BY_TIER.get(tier, 2.0)
            if provider in ("hf", "huggingface"):
                logger.info(f"HF local delay set to {self._hf_delay}s (tier={tier}, model={model})")

    # ── Public interface ──────────────────────────────────────────────────────

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1000,
        temperature: float = 0.0,
        response_format: str = None,
    ) -> str:
        """Send a completion request. Returns the response text."""
        dispatch = {
            "anthropic":   self._anthropic,
            "openai":      self._openai,
            "google":      self._google,
            "ollama":      lambda s, u, mt, t: self._ollama(s, u, mt, t, response_format),
            "huggingface": self._huggingface_api,
            "hf":          self._huggingface_local,
        }
        return dispatch[self.provider](system, user, max_tokens, temperature)

    # ── Provider implementations ──────────────────────────────────────────────

    def _anthropic(self, system, user, max_tokens, temperature):
        try:
            import anthropic
        except ImportError:
            raise ImportError("pip install anthropic")
        key = self._api_key or self._settings.get_api_key("anthropic")
        if not key:
            raise ValueError("Anthropic API key not set. Set ANTHROPIC_API_KEY or configure in Settings.")
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text.strip()

    def _openai(self, system, user, max_tokens, temperature):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("pip install openai")
        key = self._api_key or self._settings.get_api_key("openai")
        if not key:
            raise ValueError("OpenAI API key not set. Set OPENAI_API_KEY or configure in Settings.")
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        )
        return resp.choices[0].message.content.strip()

    def _google(self, system, user, max_tokens, temperature):
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("pip install google-generativeai")
        key = self._api_key or self._settings.get_api_key("google")
        if not key:
            raise ValueError("Google API key not set. Set GOOGLE_API_KEY or configure in Settings.")
        genai.configure(api_key=key)
        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system,
        )
        resp = model.generate_content(
            user,
            generation_config=genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        return resp.text.strip()

    def _ollama(self, system, user, max_tokens, temperature, response_format=None):
        """Call Ollama local server via its REST API (no extra library needed)."""
        import urllib.request, json as _json
        base = self._base_url or self._settings.get("ollama_base_url") or "http://localhost:11434"
        url = f"{base.rstrip('/')}/api/chat"
        payload = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens,
                        "num_ctx": _ctx_for_ollama_model(self.model)},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        }
        if response_format == "json":
            payload["format"] = "json"
        # Thinking models (qwen3, etc.) consume num_predict tokens for the
        # internal reasoning chain before outputting content.  The caller's
        # max_tokens budget only covers the answer, so we need extra headroom.
        # Set a generous cap: 4096 thinking + max_tokens response = 4096+max_tokens.
        if any(kw in self.model.lower() for kw in _OLLAMA_THINKING_MODELS):
            caller_max = payload["options"].get("num_predict", 2000)
            payload["options"]["num_predict"] = 4096 + caller_max
        req = urllib.request.Request(
            url,
            data=_json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        import time as _time
        last_err = None
        _req_timeout = _timeout_for_ollama_model(self.model)
        _max_attempts = 5
        for _attempt in range(_max_attempts):
            try:
                with urllib.request.urlopen(req, timeout=_req_timeout) as resp:
                    data = _json.loads(resp.read())
                content = data["message"]["content"].strip()
                if content:
                    return content
                last_err = ValueError("Ollama returned empty content")
            except urllib.error.URLError as e:
                raise ConnectionError(
                    f"Cannot reach Ollama at {base}. "
                    f"Make sure Ollama is running: `ollama serve`\nError: {e}"
                )
            except Exception as e:
                last_err = e
            if _attempt < _max_attempts - 1:
                _time.sleep(2)
        raise RuntimeError(f"Ollama returned empty/invalid response after {_max_attempts} attempts: {last_err}")

    def _huggingface_api(self, system, user, max_tokens, temperature):
        """HuggingFace Inference API — serverless, rate-limited. Use for testing only."""
        try:
            from huggingface_hub import InferenceClient
        except ImportError:
            raise ImportError("pip install huggingface_hub")

        key = self._api_key or self._settings.get_api_key("huggingface")
        if not key:
            raise ValueError("HuggingFace API key not set.")

        client = InferenceClient(model=self.model, token=key)
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ]

        # Retry loop with backoff — free tier hits 429 often
        for attempt in range(4):
            try:
                resp = client.chat.completions.create(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=max(0.01, temperature),
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    wait = 30 * (attempt + 1)   # 30s, 60s, 90s
                    logger.warning(f"HF API rate limit hit, waiting {wait}s (attempt {attempt+1}/4)")
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"HF Inference API error: {err_str}")
        raise RuntimeError("HF Inference API: exceeded retry limit on rate limiting.")

    def _huggingface_local(self, system, user, max_tokens, temperature):
        """
        Local HuggingFace inference via transformers.

        Key guarantees:
        - Model loads ONCE into _HF_MODEL_CACHE, reused for every row.
        - Hard GPU assertion at startup — job fails immediately and loudly
          if CUDA is not visible, instead of silently running on CPU for hours.
        - Uses 'dtype' kwarg (not deprecated 'torch_dtype').
        - apply_chat_template for correct prompt formatting per model family.
        """
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            import torch
        except ImportError:
            raise ImportError("pip install transformers accelerate torch")

        model_name = self.model

        # ── HARD GPU CHECK — fail fast, not after hours of CPU inference ──────
        # If this raises, run fix_cuda_env.sh on the login node first.
        if not torch.cuda.is_available():
            raise RuntimeError(
                "\n"
                "  ╔══════════════════════════════════════════════════════════╗\n"
                "  ║  CUDA NOT AVAILABLE — job would run on CPU (unusable)   ║\n"
                "  ╠══════════════════════════════════════════════════════════╣\n"
                "  ║  PyTorch and your GPU driver versions don't match.      ║\n"
                "  ║                                                          ║\n"
                "  ║  Fix (run on login node, then resubmit):                ║\n"
                "  ║    chmod +x fix_cuda_env.sh && ./fix_cuda_env.sh        ║\n"
                "  ║                                                          ║\n"
                "  ║  Diagnose only (no changes):                            ║\n"
                "  ║    ./fix_cuda_env.sh --check                            ║\n"
                "  ╚══════════════════════════════════════════════════════════╝\n"
            )

        # ── Load once, cache forever ──────────────────────────────────────────
        if model_name not in _HF_MODEL_CACHE:
            n_gpus = torch.cuda.device_count()
            gpu_info = ", ".join(
                f"{torch.cuda.get_device_name(i)} "
                f"({torch.cuda.get_device_properties(i).total_memory // (1024**3)}GB)"
                for i in range(n_gpus)
            )
            print(f"  [HF] Loading {model_name} (first call only)")
            print(f"  [HF] GPUs: {n_gpus}x — {gpu_info}")
            t_load = time.time()

            tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=True,
            )
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            # ── dtype by GPU compute capability ──────────────────────────────
            # cc < 7.0 (P100=6.0, K80=3.7): float16 kernels unavailable → float32
            # cc 7.x   (V100, RTX 8000=7.5): float16 safe
            # cc 8.0+  (A100, H100):         bfloat16 native and preferred
            cc      = torch.cuda.get_device_capability(0)
            compute = cc[0] + cc[1] / 10
            if compute >= 8.0:
                dtype = torch.bfloat16
            elif compute >= 7.0:
                dtype = torch.float16
            else:
                dtype = torch.float32
            print(f"  [HF] GPU compute {cc[0]}.{cc[1]} → dtype={dtype}")

            hf_model = AutoModelForCausalLM.from_pretrained(
                model_name,
                device_map="auto",   # spreads across all visible GPUs
                dtype=dtype,         # 'dtype' — not deprecated 'torch_dtype'
                trust_remote_code=True,
            )
            hf_model.eval()

            # Confirm the model actually landed on GPU
            first_device = next(hf_model.parameters()).device
            if first_device.type == "cpu":
                raise RuntimeError(
                    f"Model loaded to CPU despite CUDA being available. "
                    f"VRAM may be insufficient for {model_name}. "
                    f"Try a smaller model or request more GPUs."
                )
            print(f"  [HF] Model on device: {first_device} — "
                  f"loaded in {time.time()-t_load:.1f}s")

            _HF_MODEL_CACHE[model_name] = {
                "model":     hf_model,
                "tokenizer": tokenizer,
            }
        else:
            first_device = next(_HF_MODEL_CACHE[model_name]["model"].parameters()).device
            print(f"  [HF] {model_name} reused from cache (device={first_device})")

        cached    = _HF_MODEL_CACHE[model_name]
        hf_model  = cached["model"]
        tokenizer = cached["tokenizer"]

        # ── Build prompt via chat template ────────────────────────────────────
        # Some models (Gemma-2, GLM-4) reject a "system" role and raise
        # "System role not supported". Detect this and fall back to merging
        # system into the user turn, which all models accept.
        def _build_prompt(msgs):
            return tokenizer.apply_chat_template(
                msgs, tokenize=False, add_generation_prompt=True,
            )

        if getattr(tokenizer, "chat_template", None):
            try:
                prompt = _build_prompt([
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ])
            except Exception as e:
                if "system" in str(e).lower() or "not supported" in str(e).lower():
                    # Gemma-2, GLM-4: no system role — merge into user turn
                    logger.warning(
                        f"[HF] {model_name} rejected system role ({e}) "
                        f"— merging system into user message"
                    )
                    prompt = _build_prompt([
                        {"role": "user", "content": f"{system}\n\n{user}"},
                    ])
                else:
                    raise
        else:
            logger.warning(f"[HF] {model_name} has no chat_template — plain prompt fallback")
            prompt = f"### System\n{system}\n\n### User\n{user}\n\n### Assistant\n"

        # ── Tokenise ──────────────────────────────────────────────────────────
        inputs = tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=4096,
        ).to(hf_model.device)

        input_len = inputs["input_ids"].shape[1]

        # ── Generate ──────────────────────────────────────────────────────────
        # do_sample=False (greedy) when temperature=0 — avoids the
        # "temperature must be > 0 for sampling" error some models raise.
        with torch.no_grad():
            gen_kwargs = dict(
                max_new_tokens=max_tokens,
                do_sample=False,          # greedy by default
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
            if temperature > 0:
                gen_kwargs["do_sample"]    = True
                gen_kwargs["temperature"]  = temperature
                # top_p only valid with sampling — omit to silence the warning
                # "top_p is not valid for greedy decoding"
            outputs = hf_model.generate(**inputs, **gen_kwargs)

        new_tokens = outputs[0][input_len:]
        response   = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

        if self._hf_delay > 0:
            time.sleep(self._hf_delay)

        return response

    # ── Factory methods ───────────────────────────────────────────────────────

    @classmethod
    def from_settings_llm1(cls) -> "ModelClient":
        s = get_settings()
        provider, model = s.effective_llm1_model()
        return cls(provider=provider, model=model)

    @classmethod
    def from_settings_llm2(cls) -> "ModelClient":
        s = get_settings()
        provider, model = s.effective_llm2_model()
        return cls(provider=provider, model=model)

    @classmethod
    def test_connection(cls, provider: str, model: str, api_key: str = None) -> tuple[bool, str]:
        """Quick connectivity test. Returns (success, message)."""
        try:
            client = cls(provider=provider, model=model, api_key=api_key)
            result = client.complete(
                system="You are a test assistant.",
                user="Reply with exactly: OK",
                max_tokens=10,
            )
            return True, f"✓ Connected. Response: {result[:50]}"
        except Exception as e:
            return False, f"✗ {str(e)[:200]}"