"""
strategies/baseline.py — Strategy 1: Baseline LLM
Routes ALL API calls through ModelClient.
ModelClient reads provider+model from settings — whatever user picks in UI
or passes via --model on CLI is what gets called. No hardcoded Claude.
temperature=0.0.
"""

import json, re, time
from pathlib import Path

_FEW_SHOT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "few_shot_hipaa.json"

def _load_few_shot():
    try:
        with open(_FEW_SHOT_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

_SEP = "\n" + "─" * 60 + "\n"

def _format_example_baseline(ex: dict) -> str:
    steps = "\n".join(f"  Step {i+1} — {s}" for i, s in enumerate(ex["reasoning_steps"]))
    v_sym = "✅ PERMITTED" if ex["verdict"] == "PERMITTED" else "❌ DENIED"
    return (
        f"QUESTION: {ex['question']}\n"
        f"REASONING:\n{steps}\n"
        f"**VERDICT: {v_sym}**\n"
        f"**Legal Basis:** §{ex['key_section']}"
    )

def _build_few_shot_block() -> str:
    examples = _load_few_shot()
    if not examples:
        return ""
    parts = [_format_example_baseline(e) for e in examples]
    return (
        "\nEXAMPLES (study these carefully before answering):\n\n"
        + _SEP.join(parts)
        + "\n" + "─" * 60
        + "\n\nNow answer the following new question using the same reasoning process.\n"
    )

_COT_INSTRUCTION = (
    "\nREASONING PROCESS — before stating your verdict, work through these "
    "steps explicitly in your answer:\n"
    "Step 1 — Action type: what PHI is disclosed, by whom, to whom, for what purpose?\n"
    "Step 2 — Governing section: which HIPAA section and sub-provision governs this action?\n"
    "Step 3 — Exception check: does a specific permissive exception explicitly apply? Quote it.\n"
    "Step 4 — Verdict: PERMITTED only if a clear exception applies, DENIED otherwise.\n"
)

# Multi-regulation citation patterns (same set as rag.py)
_CITATION_PATTERNS = [
    r'164\.\d+(?:\([a-z0-9]+\))*',             # HIPAA §164.xxx
    r'Art\.?\s*\d+(?:\(\d+\))?(?:\([a-z]\))?', # GDPR Art.6(1)(a)
    r'§\s*313\.\d+(?:\([a-z0-9]+\))*',          # GLBA §313.x
    r'§\s*1798\.\d+(?:\([a-z0-9]+\))*',          # CCPA §1798.x
    r'§\s*31[0-9]\.\d+(?:\([a-z0-9]+\))*',       # COPPA §312.x
    r'§\s*30[234]\b', r'§\s*40[24]\b',           # SOX §302, §404
]

def _extract_citations(text: str) -> list:
    found = set()
    for pat in _CITATION_PATTERNS:
        found.update(re.findall(pat, text, re.IGNORECASE))
    return sorted(found)
from dataclasses import dataclass, field
from typing import Optional

try:
    from connector.model_client import ModelClient
    from connector.settings import get_settings
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from connector.model_client import ModelClient
    from connector.settings import get_settings


_REG_NAMES = {
    "hipaa": "HIPAA (Health Insurance Portability and Accountability Act, 45 CFR §164)",
    "gdpr":  "GDPR (EU General Data Protection Regulation)",
    "glba":  "GLBA (Gramm-Leach-Bliley Act, 15 U.S.C. §§6801-6827)",
    "ccpa":  "CCPA (California Consumer Privacy Act, Cal. Civ. Code §§1798.100-1798.199)",
    "coppa": "COPPA (Children's Online Privacy Protection Act, 16 CFR §312)",
    "sox":   "SOX (Sarbanes-Oxley Act, §§302/404)",
}

_REG_CITE_EXAMPLES = {
    "hipaa": "e.g. §164.502, §164.506, §164.508",
    "gdpr":  "e.g. Art.6(1)(a), Art.9(2)(h), Art.17(1)",
    "glba":  "e.g. §313.10, §313.14, §313.15",
    "ccpa":  "e.g. §1798.100, §1798.110, §1798.120",
    "coppa": "e.g. §312.5, §312.6, §312.8",
    "sox":   "e.g. §302, §404, §802",
}

def _build_system(regulation: str, style: str = "zero_shot") -> str:
    name  = _REG_NAMES.get(regulation, regulation.upper())
    cites = _REG_CITE_EXAMPLES.get(regulation, "specific section numbers")
    cot   = _COT_INSTRUCTION if style in ("cot", "few_shot_cot") else ""
    fs    = _build_few_shot_block() if style in ("few_shot", "few_shot_cot") else ""
    return (
        f"You are a regulatory compliance expert specializing in {name}.\n"
        f"Answer the user's question about whether an action is permitted under {name}.\n"
        f"{cot}{fs}\n"
        f"VERDICT RULE (mandatory): Output ONLY ✅ PERMITTED or ❌ DENIED. Never output\n"
        f'"Depends", "Conditional", "Unable to Determine", or any other value.\n'
        f"All nuance belongs in the Conditions or Exceptions section.\n\n"
        f"**VERDICT: [✅ PERMITTED / ❌ DENIED]**\n"
        f"**Answer:** [2-3 sentences directly answering the question.]\n"
        f"**Legal Basis:** [Specific {name} sections that apply ({cites}).]\n"
        f"**Conditions or Exceptions:** [If any.]"
    )


@dataclass
class BaselineResult:
    strategy: str = "baseline"; question: str = ""; verdict: str = ""
    answer: str = ""; citations: list = field(default_factory=list)
    latency_seconds: float = 0.0; error: str = ""
    model: str = ""; provider: str = ""; llm_raw: str = ""


_AMBIGUOUS_WORDS = ("DEPENDS", "CONDITIONAL", "UNABLE TO", "UNCERTAIN", "UNCLEAR",
                    "CONTEXT-DEPENDENT", "CASE-BY-CASE")

def _verdict(t: str) -> str:
    import re as _re
    # Priority 1: check the structured VERDICT line (avoids false matches in body text)
    m = _re.search(r'\*{0,2}VERDICT:?\*{0,2}\s*([^\n]{0,80})', t, _re.IGNORECASE)
    if m:
        line = m.group(1).upper()
        # If LLM ignored the binary-verdict rule and output an ambiguous answer, default DENIED
        if any(w in line for w in _AMBIGUOUS_WORDS): return "DENIED"
        if "✅" in line or ("PERMITTED" in line and "NOT PERMITTED" not in line): return "PERMITTED"
        if "❌" in line or "DENIED" in line or "NOT PERMITTED" in line: return "DENIED"
    # Priority 2: first 120 chars (verdict usually appears at top of response)
    first = t[:120].upper()
    if "✅" in first: return "PERMITTED"
    if "❌" in first: return "DENIED"
    if "PERMITTED" in first and "NOT PERMITTED" not in first: return "PERMITTED"
    if "DENIED" in first or "NOT PERMITTED" in first: return "DENIED"
    # Priority 3: full-text scan (lower confidence fallback)
    u = t.upper()
    if "✅" in u or ("PERMITTED" in u and "NOT PERMITTED" not in u): return "PERMITTED"
    if "❌" in u or "DENIED" in u or "NOT PERMITTED" in u: return "DENIED"
    return "DENIED"  # default-deny for ambiguous output


class BaselineStrategy:
    def __init__(self, api_key=None, model=None, prompt_style: str = "zero_shot"):
        s = get_settings()
        if model and "/" in str(model):
            parts = str(model).split("/", 1)
            self._provider, self._model = parts[0], parts[1]
        elif model:
            self._provider, self._model = s["llm1_provider"], str(model)
        else:
            self._provider, self._model = s["llm1_provider"], s["llm1_model"]
        self._api_key = api_key
        self._style   = prompt_style

    def _call(self, user: str, max_tokens=1000, system: str = "") -> str:
        return ModelClient(
            provider=self._provider, model=self._model, api_key=self._api_key
        ).complete(system=system, user=user, max_tokens=max_tokens)

    def run(self, question: str) -> BaselineResult:
        t0 = time.time()
        regulation = get_settings().get("active_regulation", "hipaa")
        system = _build_system(regulation, self._style)
        try:
            text = self._call(question, system=system)
            return BaselineResult(
                question=question, verdict=_verdict(text), answer=text,
                citations=_extract_citations(text),
                latency_seconds=round(time.time()-t0, 2),
                model=self._model, provider=self._provider, llm_raw=text,
            )
        except Exception as e:
            return BaselineResult(
                question=question, verdict="ERROR", error=str(e),
                latency_seconds=round(time.time()-t0, 2),
                model=self._model, provider=self._provider,
            )
