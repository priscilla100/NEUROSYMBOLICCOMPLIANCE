"""
app/regulation_router.py
─────────────────────────────────────────────────────────────────────────────
RegulationRouter: central dispatcher that routes compliance questions to the
correct strategy implementation based on the active regulation.

Routing table:
  baseline  — all regs  → BaselineStrategy.run()        (already reg-aware)
  rag       — all regs  → RAGStrategy.run()              (already reg-aware)
  formal    — HIPAA     → FormalStrategy.run()            (LLM1Extractor + Soufflé)
            — non-HIPAA → NonHIPAAExtractor → FormalStrategy.run_with_scenario()
  agentic   — HIPAA     → AgenticStrategy.run()           (Agents A/B/C + Soufflé)
            — non-HIPAA → NonHIPAAExtractor → FormalStrategy.run_with_scenario()
                          result wrapped as AgenticResult for UI compatibility

Why non-HIPAA formal/agentic are re-routed:
  LLM1Extractor uses a 50KB HIPAA-specific AGENT_PROMPT.md. Appending 150-word
  regulation hints is insufficient — the model still outputs HIPAA attribute/purpose
  constants (e.g. "lab-results"/"treatment") instead of what each regulation's
  Soufflé engine expects (e.g. GDPR: "health-data"/"legitimate-interests").
  NonHIPAAExtractor uses a short (~30-line) focused prompt per regulation.
"""

import os, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "app"))

try:
    from connector.settings import get_settings
    from connector.non_hipaa_extractor import NonHIPAAExtractor
    from strategies.baseline import BaselineStrategy, BaselineResult
    from strategies.rag import RAGStrategy
    from strategies.formal import FormalStrategy, FormalResult
    from strategies.agentic import AgenticStrategy, AgenticResult, AgentTrace
except ImportError:
    # Fallback for direct execution / batch runner context
    sys.path.insert(0, str(PROJECT_ROOT / "app"))
    from connector.settings import get_settings
    from connector.non_hipaa_extractor import NonHIPAAExtractor
    from strategies.baseline import BaselineStrategy, BaselineResult
    from strategies.rag import RAGStrategy
    from strategies.formal import FormalStrategy, FormalResult
    from strategies.agentic import AgenticStrategy, AgenticResult, AgentTrace


def _get_rag(session_state=None):
    """
    Return a RAGStrategy, keyed by active regulation.
    When called from Streamlit, pass st.session_state to enable caching.
    Otherwise constructs a fresh instance (for CLI / batch use).
    """
    cur_reg   = get_settings().get("active_regulation", "hipaa")
    cache_key = f"rag_instance_{cur_reg}"

    if session_state is not None:
        if session_state.get(cache_key) is None:
            r = RAGStrategy()
            try:
                r.build_index()
            except Exception:
                pass
            session_state[cache_key] = r
        return session_state[cache_key]

    # No session state (CLI / batch) — fresh instance
    r = RAGStrategy()
    try:
        r.build_index()
    except Exception:
        pass
    return r


def _wrap_as_agentic(formal_result: FormalResult, regulation: str) -> AgenticResult:
    """
    Convert a FormalResult into an AgenticResult for UI compatibility.
    Adds synthetic traces that show what happened inside the non-HIPAA path.
    """
    traces = [
        AgentTrace(
            agent=f"NonHIPAAExtractor ({regulation.upper()})",
            input_summary=formal_result.question[:120],
            output_summary=formal_result.scenario_json[:120],
            latency=0.0,
            success=True,
            notes=f"Bypassed AGENT_PROMPT.md — used short {regulation.upper()} prompt",
        ),
        AgentTrace(
            agent="Soufflé Engine",
            input_summary=formal_result.generated_facts[:120] if formal_result.generated_facts else "",
            output_summary=f"verdict={formal_result.verdict}",
            latency=formal_result.latency_seconds,
            success=formal_result.verdict not in ("ERROR",),
            notes=formal_result.error or "",
        ),
    ]
    return AgenticResult(
        strategy="agentic",
        question=formal_result.question,
        run_id=formal_result.run_id,
        run_dir=formal_result.run_dir,
        verdict=formal_result.verdict,
        answer=formal_result.answer,
        citations=formal_result.citations,
        explanation_tree=formal_result.explanation_tree,
        scenario_json=formal_result.scenario_json,
        generated_facts=formal_result.generated_facts,
        traces=traces,
        retry_count=0,
        latency_seconds=formal_result.latency_seconds,
        error=formal_result.error,
        model=get_settings().get("llm1_model", ""),
        provider=get_settings().get("llm1_provider", ""),
    )


class RegulationRouter:
    """
    Routes a compliance question to the correct strategy implementation.

    Usage:
        result = RegulationRouter().run("formal", question)
        result = RegulationRouter(session_state=st.session_state).run("rag", question)
    """

    def __init__(self, session_state=None):
        self._session_state = session_state

    def run(self, strategy: str, question: str, progress_callback=None):
        regulation = get_settings().get("active_regulation", "hipaa")

        if strategy == "baseline":
            return BaselineStrategy().run(question)

        if strategy == "rag":
            return _get_rag(self._session_state).run(question)

        if strategy in ("formal", "agentic"):
            if regulation == "hipaa":
                # HIPAA: use existing paths unchanged
                if strategy == "formal":
                    return FormalStrategy().run(question, progress_callback=progress_callback)
                else:
                    return AgenticStrategy().run(question, progress_callback=progress_callback)

            # Non-HIPAA: bypass AGENT_PROMPT.md with regulation-specific extractor
            try:
                extractor = NonHIPAAExtractor(regulation)
                scenario, scenario_json = extractor.extract(question)
            except Exception as e:
                err_msg = f"NonHIPAAExtractor ({regulation}): {e}"
                if strategy == "formal":
                    return FormalResult(
                        question=question, verdict="ERROR", error=err_msg
                    )
                else:
                    return AgenticResult(
                        question=question, verdict="ERROR", error=err_msg
                    )

            formal_result = FormalStrategy().run_with_scenario(scenario, question, scenario_json)

            if strategy == "agentic":
                return _wrap_as_agentic(formal_result, regulation)
            return formal_result

        # Unknown strategy — return an error result
        return BaselineResult(
            question=question, verdict="ERROR",
            error=f"Unknown strategy: {strategy!r}",
        )
