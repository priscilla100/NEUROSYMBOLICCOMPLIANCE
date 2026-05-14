"""
connector/llm2_explainer.py — LLM2: Explainer
Routes through ModelClient. No hardcoded Anthropic. temperature=0.0.
"""

from typing import Optional

try:
    from connector.model_client import ModelClient
    from connector.settings import get_settings
    from connector.hipaa_engine import EngineResult
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from connector.model_client import ModelClient
    from connector.settings import get_settings
    from connector.hipaa_engine import EngineResult


_REG_NAMES = {
    "hipaa": "HIPAA (45 CFR §164)",
    "gdpr":  "GDPR (EU General Data Protection Regulation)",
    "glba":  "GLBA (Gramm-Leach-Bliley Act)",
    "ccpa":  "CCPA (California Consumer Privacy Act)",
    "coppa": "COPPA (Children's Online Privacy Protection Act, 16 CFR §312)",
    "sox":   "SOX (Sarbanes-Oxley Act)",
}

def _build_system(regulation: str) -> str:
    name = _REG_NAMES.get(regulation, regulation.upper())
    return f"""You are a regulatory compliance communication specialist specializing in {name}.
A formal logic engine has determined the compliance verdict under {name}.
Your job is ONLY to explain that result clearly using {name} terminology and section references.
Do NOT reference or cite any other regulation (e.g., do not cite HIPAA sections if the question is about GDPR).
Do not add reasoning not in the explanation tree. Never contradict the formal verdict.

VERDICT MAPPING RULE (mandatory):
- If the engine verdict is ALLOWED or PERMITTED → output ✅ PERMITTED
- If the engine verdict is DENIED → output ❌ DENIED
- If the engine verdict is UNKNOWN → output ❓ UNKNOWN and explain which required fact
  the extractor could not determine from the question (do NOT output DENIED or PERMITTED).
- If the engine verdict is ERROR → output ⚠️ ERROR and describe the issue.
- Never contradict the formal engine verdict.

**VERDICT: [✅ PERMITTED / ❌ DENIED]**
**Answer:** [2-3 sentences directly answering the user's question under {name}.]
**Why:** [Legal reasoning from the citation tree in {name} terms. If no citation tree is available, explain what {name} requires for this type of action.]
**Relevant {name} Sections:** [Each cited section with a one-line plain English description.]
**Exceptions or Conditions:** [Only if applicable — edge cases, caveats, conditions.]

Tone: professional but plain — suitable for a compliance officer, auditor, or end user.""".strip()


class LLM2Explainer:
    def __init__(self, api_key=None, model=None):
        s = get_settings()
        if model and "/" in str(model):
            parts = str(model).split("/", 1)
            self._provider, self._model = parts[0], parts[1]
        elif model:
            self._provider, self._model = s["llm2_provider"], str(model)
        else:
            self._provider, self._model = s["llm2_provider"], s["llm2_model"]
        self._api_key = api_key

    def explain(self, question: str, result: EngineResult) -> str:
        regulation = get_settings().get("active_regulation", "hipaa")
        system = _build_system(regulation)
        msg = self._build_msg(question, result, regulation)
        return ModelClient(
            provider=self._provider, model=self._model, api_key=self._api_key
        ).complete(system=system, user=msg, max_tokens=1000)

    def _build_msg(self, question: str, result: EngineResult, regulation: str = "hipaa") -> str:
        s = result.scenario
        reg_name = _REG_NAMES.get(regulation, regulation.upper())
        lines = [
            f"QUESTION: {question}",
            f"REGULATION: {reg_name}",
            f"VERDICT: {result.verdict}",
            f"SENDER: {s.sender} ({s.sender_role})",
            f"RECEIVER: {s.receiver} ({s.receiver_role})",
            f"ATTRIBUTE/DATA: {s.attribute}   PURPOSE/BASIS: {s.purpose}",
        ]
        if result.citations:
            lines.append(f"CITATIONS: {', '.join(result.citations)}")
        if result.explanation_tree:
            lines.append(f"EXPLANATION TREE:\n{result.explanation_tree}")
        if result.verdict == "DENIED":
            lines.append(f"NOTE: No {reg_name} permission rule matched (closed-world). Explain what {reg_name} requires for this type of action.")
        if result.verdict == "UNKNOWN":
            lines.append(
                f"NOTE: The formal Soufflé engine returned UNKNOWN — no rule fired. "
                f"Do NOT output a DENIED or PERMITTED verdict. Output ❓ UNKNOWN. "
                f"Explain: (1) what specific fact or oracle predicate the extractor likely "
                f"failed to populate (e.g. is_public_issuer, is_audit_record, has_opted_out), "
                f"and (2) what additional information from the question would be needed for "
                f"the engine to reach a definitive verdict under {reg_name}."
            )
        if result.verdict == "ERROR":
            lines.append(f"ENGINE ERROR: {result.error_message}")
        return "\n".join(lines)
