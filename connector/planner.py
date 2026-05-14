"""
connector/planner.py
─────────────────────────────────────────────────────────────────────────────
Planning phase pre-processor for ambiguous or first-person compliance questions.

The formal pipeline expects third-person canonical questions such as:
    "Can a hospital share a patient's lab results with their insurer?"

Users naturally ask first-person or relational questions:
    "Can I access my wife's medical records?"
    "My doctor wants to share my diagnosis with my employer. Is that allowed?"

This module detects such questions, calls the LLM once to produce a canonical
rephrasing, and passes that rephrased question to LLM1 for fact extraction.
The rephrasing improves extraction accuracy without changing the legal question.
"""

from __future__ import annotations
import re
from typing import Optional

try:
    from connector.model_client import ModelClient
    from connector.settings import get_settings
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from connector.model_client import ModelClient
    from connector.settings import get_settings


PLANNER_SYSTEM = """\
You are a HIPAA compliance question normalizer. Your only job is to rewrite
ambiguous, first-person, or relational compliance questions into a clear
third-person canonical form that explicitly names:
  - who is sharing (sender and their role)
  - who receives (receiver and their role)
  - what protected health information is involved
  - the purpose of the disclosure

Rules:
  - Resolve "I" using context (patient if asking about their own records,
    provider if asking about disclosing to someone else)
  - Resolve relationship terms to legal/medical roles:
      wife / husband / spouse  →  patient's spouse (or legal guardian if appropriate)
      child / son / daughter   →  minor patient
      parent / mother / father →  parent / legal guardian
  - Output ONLY the rephrased question (one or two clear sentences), no preamble
  - If the question is already third-person and unambiguous, output it unchanged

Examples:
  IN:  Can I access my wife's medical records?
  OUT: Can a patient access their spouse's medical records held by a hospital?

  IN:  My doctor wants to send my test results to my insurance company.
  OUT: Can a physician disclose a patient's lab test results to a health insurance company for claims processing?

  IN:  Can a hospital share patient records with police?
  OUT: Can a hospital share patient records with law enforcement?
"""

# Patterns that indicate a planning step is likely needed
_FIRST_PERSON_RE = re.compile(
    r"\b(can i|my |i am|i\'m|i need|i want|i have|i asked|am i|we |our )\b",
    re.IGNORECASE,
)
_RELATIONAL_RE = re.compile(
    r"\b(wife|husband|spouse|child|son|daughter|parent|mother|father|"
    r"brother|sister|partner|family member|loved one|relative|caregiver)\b",
    re.IGNORECASE,
)


class QuestionPlanner:
    """
    Detect and rephrase ambiguous compliance questions before formal analysis.

    Usage:
        planner = QuestionPlanner()
        result  = planner.plan(question)
        canonical_q   = result["rephrased"]
        was_rephrased = result["was_rephrased"]
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key

    def needs_planning(self, question: str) -> bool:
        """Return True if the question is first-person or uses relational terms."""
        return bool(
            _FIRST_PERSON_RE.search(question) or
            _RELATIONAL_RE.search(question)
        )

    def plan(self, question: str) -> dict:
        """
        Rephrase the question if needed.

        Returns
        -------
        dict with keys:
            original      : str  — the original question
            rephrased     : str  — canonical form (unchanged if no planning needed)
            was_rephrased : bool
            plan_notes    : str  — human-readable explanation of what changed
        """
        if not self.needs_planning(question):
            return {
                "original":      question,
                "rephrased":     question,
                "was_rephrased": False,
                "plan_notes":    "",
            }

        s        = get_settings()
        provider = s.get("llm1_provider", "ollama")
        model    = s.get("llm1_model",    "llama3.2:latest")

        try:
            client    = ModelClient(provider=provider, model=model, api_key=self._api_key)
            rephrased = client.complete(
                system    = PLANNER_SYSTEM,
                user      = question,
                max_tokens = 200,
                temperature = 0.0,
            ).strip()
        except Exception as e:
            # Planning failure is non-fatal — proceed with original question
            return {
                "original":      question,
                "rephrased":     question,
                "was_rephrased": False,
                "plan_notes":    f"Planning skipped (LLM call failed: {e})",
            }

        return {
            "original":      question,
            "rephrased":     rephrased,
            "was_rephrased": rephrased.lower() != question.lower(),
            "plan_notes":    f'Rephrased from: "{question}"',
        }
