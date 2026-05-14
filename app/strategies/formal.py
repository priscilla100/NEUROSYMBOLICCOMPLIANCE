"""
strategies/formal.py
────────────────────────────────────────────────────────────────────────────
Strategy 3 — Formal Souffle Engine

This is the core formal approach. Key behavior you asked about:

  PERSISTENT ARTIFACTS: Every run writes its facts file and output CSVs
  to a named directory under runs/ so you can inspect them after the fact.
  The temp directory is still used during execution, but the artifacts
  are copied to runs/<run_id>/ before cleanup.

  Run directory structure:
      runs/
      └── run_20250415_143022_abc123/
          ├── hipaa_query_facts.dl      ← the Datalog input we generated
          ├── hipaa_query_main.dl       ← the main include file
          ├── output/
          │   ├── is_disclosure_allowed.csv
          │   ├── is_disclosure_denied.csv
          │   ├── disclosure_attempted.csv
          │   ├── permitted_by_164_502.csv
          │   ├── permitted_by_164_506.csv
          │   ├── excluded_164_502_b_2.csv
          │   ├── minimum_necessary_satisfied.csv
          │   └── is_personal_representative.csv
          └── result.json              ← verdict + metadata
"""

import os
import csv
import re
import time
import json
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from connector import config
    from connector.hipaa_engine import (
        DatalogScenario, EngineResult, scenario_to_datalog,
        find_souffle, OPTIONAL_SECTIONS, REQUIRED_SECTIONS,
        _extract_citations,
    )
    from connector.llm1_extractor import LLM1Extractor
    from connector.llm2_explainer import LLM2Explainer
    from connector.settings import get_settings
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from connector import config
    from connector.hipaa_engine import (
        DatalogScenario, EngineResult, scenario_to_datalog,
        find_souffle, OPTIONAL_SECTIONS, REQUIRED_SECTIONS,
        _extract_citations,
    )
    from connector.llm1_extractor import LLM1Extractor
    from connector.llm2_explainer import LLM2Explainer
    from connector.settings import get_settings

# ── Regulation → Souffle file mapping ─────────────────────────────────────
# Each regulation has: required files (always included), optional (if present),
# and final files (included last, after required+optional).
REGULATION_FILES = {
    "hipaa": {
        "required": [
            "hipaa_types.dl", "hipaa_hierarchies.dl", "hipaa_macros.dl",
            "hipaa_stubs.dl", "hipaa_164_506.dl",
        ],
        "optional": [
            "hipaa_164_508.dl", "hipaa_164_510.dl",
            "hipaa_164_512.dl", "hipaa_164_514.dl", "hipaa_164_524.dl",
        ],
        "final": ["hipaa_164_502.dl", "hipaa_top.dl"],
    },
    # Non-HIPAA top files already #include their constituent files,
    # so we use only the top file to avoid double-inclusion errors.
    "gdpr":  {"required": [], "optional": [], "final": ["gdpr_top.dl"]},
    "glba":  {"required": [], "optional": [], "final": ["glba_top.dl"]},
    "ccpa":  {"required": [], "optional": [], "final": ["ccpa_top.dl"]},
    "coppa": {"required": [], "optional": [], "final": ["coppa_top.dl"]},
    "sox":   {"required": [], "optional": [], "final": ["sox_top.dl"]},
}


@dataclass
class FormalResult:
    strategy: str = "formal"
    question: str = ""
    run_id: str = ""
    run_dir: str = ""            # path to the persistent artifact directory
    verdict: str = ""            # ALLOWED | DENIED | ERROR | UNKNOWN
    answer: str = ""             # LLM2 plain English explanation
    citations: list = field(default_factory=list)
    explanation_tree: str = ""
    scenario_json: str = ""
    generated_facts: str = ""
    latency_seconds: float = 0.0
    error: str = ""
    llm_raw: str = ""
    precedence_graph_dot: str = ""   # DOT source from --show=precedence-graph
    html_report_path: str = ""       # path to souffle_report.html (if generated)
    explain_output: str = ""         # captured output from souffle -t explain

    @property
    def facts_file(self) -> str:
        # Glob for any *_query_facts.dl file in run_dir
        if not self.run_dir:
            return ""
        import glob as _glob
        matches = _glob.glob(os.path.join(self.run_dir, "*_query_facts.dl"))
        return matches[0] if matches else ""

    @property
    def output_dir(self) -> str:
        return os.path.join(self.run_dir, "output") if self.run_dir else ""


class FormalStrategy:
    """
    Strategy 3: LLM1 → Souffle engine → LLM2.
    Writes persistent artifacts to runs/<run_id>/.

    Parameters
    ----------
    runs_dir : str
        Where to save run artifacts. Defaults to <project_root>/runs/
    """

    def __init__(
        self,
        runs_dir: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.extractor = LLM1Extractor(api_key=api_key)
        self.explainer = LLM2Explainer(api_key=api_key)

        project_root = Path(config.DATALOG_ENGINE_DIR).parent
        self.runs_dir = runs_dir or str(project_root / "runs")
        os.makedirs(self.runs_dir, exist_ok=True)

        try:
            self.souffle_binary = find_souffle()
        except RuntimeError as e:
            self.souffle_binary = None
            self._souffle_error = str(e)

    def run(self, question: str, progress_callback=None) -> FormalResult:
        t0 = time.time()

        def _cb(msg: str):
            if progress_callback:
                progress_callback(msg)

        # Generate run ID
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        run_dir = os.path.join(self.runs_dir, f"run_{run_id}")
        os.makedirs(run_dir, exist_ok=True)

        # Step 1: Extract scenario
        # For non-HIPAA regulations, use NonHIPAAExtractor (short focused prompt)
        # instead of LLM1Extractor (50KB HIPAA AGENT_PROMPT.md).
        regulation = get_settings().get("active_regulation", "hipaa")
        _cb("Step 1/3 — Sending question to LLM1 (fact extraction)")
        try:
            if regulation != "hipaa":
                try:
                    from connector.non_hipaa_extractor import NonHIPAAExtractor
                except ImportError:
                    import sys as _sys
                    _sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
                    from connector.non_hipaa_extractor import NonHIPAAExtractor
                extractor = NonHIPAAExtractor(regulation)
                scenario, raw_json = extractor.extract(question)
            else:
                scenario, raw_json = self.extractor.extract(question)
            _llm_raw = getattr(extractor if regulation != "hipaa" else self.extractor,
                               '_last_raw_response', raw_json)
        except Exception as e:
            _cb(f"Step 1/3 — LLM1 extraction failed: {e}")
            _captured_raw = getattr(self.extractor, '_last_raw_response', '')
            return FormalResult(
                question=question, run_id=run_id, run_dir=run_dir,
                verdict="ERROR", error=f"LLM1 extraction failed: {e}",
                latency_seconds=round(time.time() - t0, 2),
                llm_raw=_captured_raw,
            )

        _cb(f"Step 1/3 ✓ LLM1 extracted scenario (sender={scenario.sender_role}, "
            f"receiver={scenario.receiver_role}, attribute={scenario.attribute})")

        # Step 2: Run Souffle
        if not self.souffle_binary:
            _cb("Step 2/3 — ERROR: Soufflé binary not found")
            return FormalResult(
                question=question, run_id=run_id, run_dir=run_dir,
                verdict="ERROR", error=getattr(self, '_souffle_error', 'Souffle not found'),
                scenario_json=raw_json,
                latency_seconds=round(time.time() - t0, 2),
                llm_raw=_llm_raw,
            )

        _cb("Step 2/3 — Running Soufflé formal engine")
        engine_result = self._run_souffle(scenario, run_dir)
        _cb(f"Step 2/3 ✓ Soufflé verdict: {engine_result.verdict}"
            + (f"  citations: {', '.join(engine_result.citations)}" if engine_result.citations else ""))

        # Step 2b: Supplemental debug artifacts (precedence graph + explain proof tree)
        main_path = os.path.join(run_dir, f"{regulation}_query_main.dl")
        pg_dot       = self._generate_precedence_graph(main_path, config.DATALOG_ENGINE_DIR)
        explain_out  = self._run_souffle_explain(
            engine_result.scenario, main_path, run_dir, verdict=engine_result.verdict
        )
        html_report_path = os.path.join(run_dir, "souffle_report.html")
        if not os.path.exists(html_report_path):
            html_report_path = ""

        # Step 3: LLM2 explanation
        _cb("Step 3/3 — Sending verdict to LLM2 (explanation generation)")
        try:
            answer = self.explainer.explain(question, engine_result)
        except Exception as e:
            answer = f"(Explanation generation failed: {e})"
            _cb(f"Step 3/3 — LLM2 explanation failed: {e}")

        result = FormalResult(
            question=question,
            run_id=run_id,
            run_dir=run_dir,
            verdict=engine_result.verdict,
            answer=answer,
            citations=engine_result.citations,
            explanation_tree=engine_result.explanation_tree,
            scenario_json=raw_json,
            generated_facts=engine_result.generated_facts,
            latency_seconds=round(time.time() - t0, 2),
            error=engine_result.error_message,
            precedence_graph_dot=pg_dot,
            html_report_path=html_report_path,
            explain_output=explain_out,
            llm_raw=_llm_raw,
        )

        _cb(f"Step 3/3 ✓ Done — verdict: {result.verdict}  ({result.latency_seconds}s)")
        # Save result metadata
        self._save_result_json(result, run_dir, question)
        return result

    def run_with_scenario(
        self,
        scenario: DatalogScenario,
        question: str,
        scenario_json: str = "",
    ) -> FormalResult:
        """
        Skip LLM1 extraction — use a pre-built scenario directly.
        Used by RegulationRouter for non-HIPAA regulations so that
        NonHIPAAExtractor (short prompt) replaces LLM1Extractor (50KB HIPAA prompt).
        """
        t0 = time.time()
        run_id  = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        run_dir = os.path.join(self.runs_dir, f"run_{run_id}")
        os.makedirs(run_dir, exist_ok=True)

        if not self.souffle_binary:
            return FormalResult(
                question=question, run_id=run_id, run_dir=run_dir,
                verdict="ERROR", error=getattr(self, '_souffle_error', 'Souffle not found'),
                scenario_json=scenario_json,
                latency_seconds=round(time.time() - t0, 2),
            )

        engine_result = self._run_souffle(scenario, run_dir)

        regulation   = get_settings().get("active_regulation", "hipaa")
        main_path    = os.path.join(run_dir, f"{regulation}_query_main.dl")
        pg_dot       = self._generate_precedence_graph(main_path, config.DATALOG_ENGINE_DIR)
        explain_out  = self._run_souffle_explain(
            scenario, main_path, run_dir, verdict=engine_result.verdict
        )
        html_report_path = os.path.join(run_dir, "souffle_report.html")
        if not os.path.exists(html_report_path):
            html_report_path = ""

        try:
            answer = self.explainer.explain(question, engine_result)
        except Exception as e:
            answer = f"(Explanation generation failed: {e})"

        result = FormalResult(
            question=question,
            run_id=run_id,
            run_dir=run_dir,
            verdict=engine_result.verdict,
            answer=answer,
            citations=engine_result.citations,
            explanation_tree=engine_result.explanation_tree,
            scenario_json=scenario_json,
            generated_facts=engine_result.generated_facts,
            latency_seconds=round(time.time() - t0, 2),
            error=engine_result.error_message,
            precedence_graph_dot=pg_dot,
            html_report_path=html_report_path,
            explain_output=explain_out,
        )
        self._save_result_json(result, run_dir, question)
        return result

    def _generate_precedence_graph(self, main_path: str, proj: str) -> str:
        """Run souffle --show=precedence-graph and return DOT source, or '' on failure."""
        if not self.souffle_binary or not os.path.exists(main_path):
            return ""
        try:
            pg = subprocess.run(
                [self.souffle_binary, "--show=precedence-graph", main_path],
                capture_output=True, text=True, timeout=10, cwd=proj,
            )
            dot = pg.stdout.strip()
            if not dot:
                # Some Soufflé versions write to a .dot file instead of stdout
                stem = os.path.splitext(os.path.basename(main_path))[0]
                for candidate in (
                    os.path.join(proj, f"{stem}-precedence_graph.dot"),
                    os.path.join(proj, "precedence_graph.dot"),
                    os.path.join(os.path.dirname(main_path), "precedence_graph.dot"),
                ):
                    if os.path.exists(candidate):
                        dot = open(candidate).read().strip()
                        break
            if dot:
                dot_path = os.path.join(os.path.dirname(main_path), "precedence_graph.dot")
                with open(dot_path, "w") as f:
                    f.write(dot)
            return dot
        except Exception:
            return ""

    def _run_souffle_explain(
        self,
        scenario: "DatalogScenario",
        main_path: str,
        run_dir: str,
        verdict: str = "UNKNOWN",
    ) -> str:
        """
        Run souffle -t explain --explain-negation non-interactively.

        For ALLOWED verdicts: pipes `explain is_disclosure_allowed(...)` — positive proof tree.
        For DENIED verdicts:  pipes `explainne is_disclosure_allowed(...)` — negation proof tree
          showing which sub-goals failed, powered by Soufflé's --explain-negation flag.

        Returns the captured proof-tree text, or '' on failure.
        """
        if not self.souffle_binary or not os.path.exists(main_path):
            return ""
        p1 = scenario.sender
        p2 = scenario.receiver
        q  = scenario.subject
        m  = scenario.message_id
        t  = scenario.attribute
        u  = scenario.purpose

        denied = verdict in ("DENIED", "NOT PERMITTED")
        if denied:
            # For DENIED: explain is_disclosure_denied(...) — a real positive relation
            # (disclosure_attempted AND NOT is_disclosure_allowed → is_disclosure_denied).
            # Soufflé 2.5 does not support --explain-negation / explainne; using the
            # explicit is_disclosure_denied relation achieves the same effect.
            stdin_cmds = (
                f'explain is_disclosure_denied("{p1}","{p2}","{q}","{m}","{t}","{u}").\n'
                "exit.\n"
            )
        else:
            stdin_cmds = (
                f'explain is_disclosure_allowed("{p1}","{p2}","{q}","{m}","{t}","{u}").\n'
                "exit.\n"
            )
        try:
            with tempfile.TemporaryDirectory() as tmp_out:
                proc = subprocess.run(
                    [self.souffle_binary, "-D", tmp_out,
                     "-t", "explain", main_path],
                    input=stdin_cmds,
                    capture_output=True, text=True,
                    timeout=30,
                    cwd=config.DATALOG_ENGINE_DIR,
                )
            stdout_out = proc.stdout.strip()
            stderr_out = (proc.stderr or "").strip()

            # Soufflé's SubproofGenerator (explain mode) crashes with an assertion
            # failure when it encounters certain ADT variants in DENIED negation
            # proof trees (SubproofGenerator.cpp:238 "unhandled").
            # Suppress the raw C++ assertion message; use partial stdout if any,
            # otherwise fall back to the CSV-based summary built below.
            if "Assertion failed" in stderr_out or "SubproofGenerator" in stderr_out:
                output = stdout_out  # may be empty — that's fine
            elif not stdout_out and stderr_out:
                output = stderr_out
            else:
                output = stdout_out

            if output:
                explain_path = os.path.join(run_dir, "souffle_explain.txt")
                with open(explain_path, "w") as f:
                    f.write(output)
            return output
        except Exception:
            return ""

    def _run_souffle(self, scenario: DatalogScenario, run_dir: str) -> EngineResult:
        """Run Souffle, writing persistent artifacts to run_dir."""
        proj = config.DATALOG_ENGINE_DIR

        facts_text = scenario_to_datalog(scenario)
        regulation = get_settings().get("active_regulation", "hipaa")
        facts_text = FormalStrategy._adapt_facts(facts_text, regulation)
        facts_path = os.path.join(run_dir, f"{regulation}_query_facts.dl")
        with open(facts_path, "w") as f:
            f.write(facts_text)

        # Build main include file using regulation-aware file list.
        # CRITICAL: include only rule .dl files, not *_main.dl or *_facts.dl.
        # Those pull in test scenarios which corrupt result filtering.
        reg_cfg = REGULATION_FILES.get(regulation, REGULATION_FILES["hipaa"])
        lines = []
        for f in reg_cfg["required"]:
            lines.append(f'#include "{proj}/{f}"')
        for f in reg_cfg["optional"]:
            full = os.path.join(proj, f)
            if os.path.exists(full):
                lines.append(f'#include "{full}"')
        for f in reg_cfg["final"]:
            lines.append(f'#include "{proj}/{f}"')
        lines.append(f'#include "{facts_path}"')   # ONLY query facts — no test data
        main_text = "\n".join(lines) + "\n"
        main_path = os.path.join(run_dir, f"{regulation}_query_main.dl")
        with open(main_path, "w") as f:
            f.write(main_text)

        # Output goes directly into run_dir/output/ (persistent!)
        output_dir = os.path.join(run_dir, "output")
        os.makedirs(output_dir, exist_ok=True)

        report_path = os.path.join(run_dir, "souffle_report.html")
        # Note: -r HTML report uses GNU diff (--new-line-format) which is not
        # available on macOS BSD diff; omit -r to avoid returncode=1 on macOS.
        import platform as _platform
        _use_report = _platform.system() != "Darwin"
        _souffle_cmd = [self.souffle_binary, "-D", output_dir]
        if _use_report:
            _souffle_cmd += ["-r", report_path]
        _souffle_cmd.append(main_path)
        try:
            proc = subprocess.run(
                _souffle_cmd,
                capture_output=True, text=True,
                timeout=config.SOUFFLE_TIMEOUT_SECONDS,
                cwd=proj,
            )
        except subprocess.TimeoutExpired:
            return EngineResult(
                verdict="ERROR", scenario=scenario,
                error_message=f"Souffle timed out after {config.SOUFFLE_TIMEOUT_SECONDS}s.",
                generated_facts=facts_text,
            )

        with open(os.path.join(run_dir, "souffle.log"), "w") as f:
            f.write(f"returncode: {proc.returncode}\n")
            f.write(f"stdout:\n{proc.stdout}\n")
            f.write(f"stderr:\n{proc.stderr}\n")

        # Distinguish warnings from hard errors.
        # Souffle exits 1 for "no rules/facts" warnings but still writes CSVs.
        if proc.returncode != 0:
            allowed_csv = os.path.join(output_dir, "is_disclosure_allowed.csv")
            denied_csv  = os.path.join(output_dir, "is_disclosure_denied.csv")
            csvs_exist  = os.path.exists(allowed_csv) or os.path.exists(denied_csv)
            is_only_warnings = csvs_exist and "Error:" not in proc.stderr

            # Retry: if LLM injected undefined relation names or wrong-arity facts,
            # strip those lines and re-run.  LLMs sometimes invent oracle predicate
            # names not declared in the engine, or pass too many arguments to a
            # declared predicate (e.g. adding msg_id to a 5-arg relation).
            if not is_only_warnings and (
                "Undefined relation" in proc.stderr or
                "Mismatching arity" in proc.stderr
            ):
                import re as _re
                undef_rels  = set(_re.findall(r'Undefined relation (\w+)', proc.stderr))
                arity_rels  = set(_re.findall(r'Mismatching arity of relation (\w+)', proc.stderr))
                undef_rels  = undef_rels | arity_rels
                if undef_rels:
                    # Remove lines in facts_text that start with an undefined predicate
                    def _strip_undef(text: str, rels: set) -> str:
                        cleaned = []
                        for line in text.splitlines(keepends=True):
                            stripped = line.strip()
                            if any(stripped.startswith(r + "(") for r in rels):
                                continue
                            cleaned.append(line)
                        return "".join(cleaned)
                    facts_text_clean = _strip_undef(facts_text, undef_rels)
                    with open(facts_path, "w") as f:
                        f.write(facts_text_clean)
                    # Clear output dir and retry
                    import shutil as _shutil
                    _shutil.rmtree(output_dir)
                    os.makedirs(output_dir, exist_ok=True)
                    try:
                        proc = subprocess.run(
                            _souffle_cmd,
                            capture_output=True, text=True,
                            timeout=config.SOUFFLE_TIMEOUT_SECONDS,
                            cwd=proj,
                        )
                        with open(os.path.join(run_dir, "souffle.log"), "w") as f:
                            f.write(f"returncode: {proc.returncode}\n")
                            f.write(f"stdout:\n{proc.stdout}\n")
                            f.write(f"stderr:\n{proc.stderr}\n")
                        csvs_exist = (os.path.exists(allowed_csv) or
                                      os.path.exists(denied_csv))
                        is_only_warnings = csvs_exist and "Error:" not in proc.stderr
                        facts_text = facts_text_clean
                    except subprocess.TimeoutExpired:
                        return EngineResult(
                            verdict="ERROR", scenario=scenario,
                            error_message="Souffle timed out on retry.",
                            generated_facts=facts_text,
                        )

            if proc.returncode != 0 and not is_only_warnings:
                return EngineResult(
                    verdict="ERROR", scenario=scenario,
                    error_message=f"Souffle error:\n{proc.stderr[:600]}",
                    generated_facts=facts_text,
                )
            # else: only warnings — output was written, proceed

        allowed = self._read_csv(os.path.join(output_dir, "is_disclosure_allowed.csv"))
        denied  = self._read_csv(os.path.join(output_dir, "is_disclosure_denied.csv"))

        # CRITICAL: filter rows to the exact query (p1,p2,q,m,t,u) tuple.
        # Do NOT take the first row blindly — other scenarios' results must be ignored.
        p1, p2, q = scenario.sender, scenario.receiver, scenario.subject
        m, t, u   = scenario.message_id, scenario.attribute, scenario.purpose

        matching_allowed = [
            row for row in allowed
            if len(row) >= 6 and row[:6] == [p1, p2, q, m, t, u]
        ]
        matching_denied = [
            row for row in denied
            if len(row) >= 6 and row[:6] == [p1, p2, q, m, t, u]
        ]

        if matching_allowed:
            expl = matching_allowed[0][6] if len(matching_allowed[0]) > 6 else ""
            return EngineResult(
                verdict="ALLOWED", scenario=scenario,
                explanation_tree=expl, citations=self._extract_all_citations(expl),
                raw_allowed_rows=matching_allowed, raw_denied_rows=matching_denied,
                generated_facts=facts_text,
            )
        elif matching_denied:
            return EngineResult(
                verdict="DENIED", scenario=scenario,
                raw_denied_rows=matching_denied, generated_facts=facts_text,
            )
        else:
            debug = ""
            if allowed:
                debug = (f"\nQuery: ({p1},{p2},{q},{m},{t},{u})"
                         f"\nFirst CSV row: ({','.join(allowed[0][:6])})"
                         f"\nMismatch — check role/attribute/purpose string constants.")
            return EngineResult(
                verdict="UNKNOWN", scenario=scenario,
                error_message="No matching output row." + debug,
                generated_facts=facts_text,
            )

    # ── Fact adapters ──────────────────────────────────────────────────────────

    # Predicates that only exist in HIPAA Datalog files.
    # These must be stripped before writing facts for non-HIPAA regulations.
    _HIPAA_ONLY_PREDICATES = {
        "belongstorole(", "organization_member(", "is_business_associate_of(",
        "is_guardian(", "has_authority_to_act(", "provider_of(",
        "believes_minimum_necessary(", "obtained_consent_506b(",
        "satisfactory_assurances(", "obtained_authorization_164_508(",
        "believes_unlawful_conduct(", "believes_victim_of_crime(",
        "is_incident_to_use(", "is_reply_to_request(",
        "secretary_investigation_authorized(", "abuse_exception(",
        "minor_acts_as_individual(", "permitted_by_other_law(",
        "prohibited_by_other_law(",
    }

    # Each regulation's msg_contains variant
    _MSG_CONTAINS_PRED = {
        "hipaa":  "msg_contains",
        "gdpr":   "msg_contains",
        "glba":   "msg_contains_npi",
        "ccpa":   "msg_contains",
        "coppa":  "msg_contains_child_data",
        "sox":    "msg_contains_record",
    }

    @staticmethod
    def _adapt_facts(facts_text: str, regulation: str) -> str:
        """
        Strip HIPAA-specific predicates and rename msg_contains for non-HIPAA
        regulations.  For HIPAA, returns facts_text unchanged.
        """
        if regulation == "hipaa":
            return facts_text

        msg_pred = FormalStrategy._MSG_CONTAINS_PRED.get(regulation, "msg_contains")
        result_lines = []
        for line in facts_text.splitlines():
            stripped = line.strip()
            # Drop lines that are HIPAA-only predicates
            if any(stripped.startswith(p) for p in FormalStrategy._HIPAA_ONLY_PREDICATES):
                continue
            # Rename msg_contains to the regulation-appropriate predicate
            if msg_pred != "msg_contains":
                line = line.replace("msg_contains(", f"{msg_pred}(", 1)
            result_lines.append(line)

        return "\n".join(result_lines) + "\n"

    # ── Citation extraction (all regulations) ─────────────────────────────────

    @staticmethod
    def _extract_all_citations(tree: str) -> list:
        """Extract citation references from explanation tree for any regulation."""
        patterns = [
            r'164\.\d+(?:\([a-z0-9]+\))*',           # HIPAA: 164.xxx(y)(z)
            r'Art\.?\s*\d+(?:\(\d+\))?(?:\([a-z]\))?', # GDPR: Art.6(1)(a)
            r'§\s*\d+\.\d+(?:\([a-z0-9]+\))*',        # GLBA/CCPA/COPPA: §313.14
            r'§\s*1798\.\d+(?:\([a-z0-9]+\))*',        # CCPA specific
            r'§\s*31[0-9]\.\d+(?:\([a-z0-9]+\))*',     # COPPA §312.x
            r'§\s*30[0-9]\b',                           # SOX §302, §404
            r'§\s*40[0-9]\b',                           # SOX §404
        ]
        citations = set()
        for pat in patterns:
            citations.update(re.findall(pat, tree, re.IGNORECASE))
        return sorted(citations)

    def _read_csv(self, path: str) -> list:
        if not os.path.exists(path):
            return []
        with open(path, newline="") as f:
            return list(csv.reader(f, delimiter="\t"))

    def _save_result_json(self, result: FormalResult, run_dir: str, question: str):
        meta = {
            "run_id": result.run_id,
            "question": question,
            "verdict": result.verdict,
            "citations": result.citations,
            "latency_seconds": result.latency_seconds,
            "explanation_tree": result.explanation_tree,
            "error": result.error,
            "timestamp": datetime.now().isoformat(),
        }
        with open(os.path.join(run_dir, "result.json"), "w") as f:
            json.dump(meta, f, indent=2)
