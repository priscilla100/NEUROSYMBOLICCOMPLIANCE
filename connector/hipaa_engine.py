"""
connector/hipaa_engine.py
─────────────────────────────────────────────────────────────────────────────
Python ↔ Souffle bridge.

Path resolution fix: souffle_project_dir should be the ABSOLUTE path to
your datalog_engine/ folder. The engine auto-detects the souffle binary.
"""

import os
import csv
import shutil
import subprocess
import tempfile
import re
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Auto-detect souffle binary
# ─────────────────────────────────────────────────────────────────────────────

def find_souffle() -> str:
    """
    Find the souffle binary. Checks PATH first, then common install locations.
    Raises RuntimeError with install instructions if not found.
    """
    # 1. Check PATH
    found = shutil.which("souffle")
    if found:
        return found

    # 2. Common locations (macOS Homebrew, Linux)
    candidates = [
        "/opt/homebrew/bin/souffle",       # macOS Apple Silicon
        "/usr/local/bin/souffle",           # macOS Intel / Linux
        "/usr/bin/souffle",                 # Ubuntu apt
        os.path.expanduser("~/.local/bin/souffle"),
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    raise RuntimeError(
        "Souffle not found. Install it:\n"
        "  macOS:  brew install souffle-lang/souffle/souffle\n"
        "  Ubuntu: sudo apt-get install souffle\n"
        "  Docs:   https://souffle-lang.github.io/install\n"
        "Then restart your terminal."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DatalogScenario:
    """
    Structured HIPAA disclosure scenario.
    All string values must use exact Souffle hierarchy constants (lowercase, hyphenated).
    """
    # Required
    sender: str
    sender_role: str
    receiver: str
    receiver_role: str
    subject: str
    subject_category: str   # adult | unemancipated-minor | emancipated-minor | deceased
    attribute: str          # e.g. lab-results, diagnosis, medical-record
    purpose: str            # e.g. treatment, billing, research
    message_id: str = "msg_001"

    # Relationships
    same_org: bool = False
    is_business_associate: bool = False
    is_guardian_of_subject: bool = False
    has_authority_to_act: bool = False
    provider_patient: bool = False

    # Oracle predicates
    believes_minimum_necessary: bool = False
    obtained_consent_506b: bool = False
    satisfactory_assurances: bool = False
    obtained_authorization_164_508: bool = False
    believes_unlawful_conduct: bool = False
    believes_victim_of_crime: bool = False
    is_incident_to_use: bool = False
    is_reply_to_request: bool = False
    secretary_investigation_authorized: bool = False
    abuse_exception: bool = False
    minor_acts_as_individual: bool = False
    permitted_by_other_law: bool = False
    prohibited_by_other_law: bool = False

    extra_facts: list = field(default_factory=list)


@dataclass
class EngineResult:
    verdict: str                    # ALLOWED | DENIED | ERROR | UNKNOWN
    scenario: DatalogScenario
    explanation_tree: str = ""
    citations: list = field(default_factory=list)
    raw_allowed_rows: list = field(default_factory=list)
    raw_denied_rows: list = field(default_factory=list)
    error_message: str = ""
    generated_facts: str = ""       # the .dl text we sent to Souffle (for debugging)

    @property
    def is_allowed(self) -> bool:
        return self.verdict == "ALLOWED"

    @property
    def is_denied(self) -> bool:
        return self.verdict == "DENIED"

    def summary(self) -> str:
        lines = [f"VERDICT: {self.verdict}"]
        if self.citations:
            lines.append("CITATIONS: " + ", ".join(self.citations))
        if self.explanation_tree:
            lines.append("EXPLANATION TREE:\n" + self.explanation_tree)
        if self.error_message:
            lines.append(f"ERROR: {self.error_message}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Facts generator
# ─────────────────────────────────────────────────────────────────────────────

def scenario_to_datalog(s: DatalogScenario) -> str:
    lines = [
        f'// Auto-generated facts: {s.sender} → {s.receiver} [{s.attribute} / {s.purpose}]',
        "",
        "// --- Principals ---",
        f'activerole("{s.sender}", "{s.sender_role}").',
        f'activerole("{s.receiver}", "{s.receiver_role}").',
    ]
    if s.subject != s.receiver and s.subject != s.sender:
        lines.append(f'activerole("{s.subject}", "patient").')

    lines += [
        "",
        "// --- Subject category ---",
        f'belongstorole("{s.subject}", "{s.subject_category}").',
        "",
        "// --- Message ---",
        f'msg_contains("{s.message_id}", "{s.subject}", "{s.attribute}").',
        "",
    ]

    rel = []
    if s.same_org:
        rel.append(f'organization_member("{s.receiver}", "{s.sender}").')
    if s.is_business_associate:
        rel.append(f'is_business_associate_of("{s.receiver}", "{s.sender}").')
    if s.is_guardian_of_subject:
        rel.append(f'is_guardian("{s.receiver}", "{s.subject}").')
    if s.has_authority_to_act:
        rel.append(f'has_authority_to_act("{s.receiver}", "{s.subject}").')
    if s.provider_patient:
        rel.append(f'provider_of("{s.sender}", "{s.subject}").')
    if rel:
        lines += ["// --- Relationships ---"] + rel + [""]

    p1, p2, q, m, t, u = s.sender, s.receiver, s.subject, s.message_id, s.attribute, s.purpose
    oracles = []
    if s.believes_minimum_necessary:
        oracles.append(f'believes_minimum_necessary("{p1}","{p2}","{q}","{m}","{t}","{u}").')
    if s.obtained_consent_506b:
        oracles.append(f'obtained_consent_506b("{p1}","{p2}","{q}","{t}","{u}").')
    if s.satisfactory_assurances:
        oracles.append(f'satisfactory_assurances("{p1}","{p2}","{q}","{t}","{u}").')
    if s.obtained_authorization_164_508:
        oracles.append(f'obtained_authorization_164_508("{p1}","{p2}","{q}","{t}","{u}").')
    if s.believes_unlawful_conduct:
        # believes_unlawful_conduct(employee, employer) — NOT (employee, receiver).
        # Find employer from extra_facts if present, otherwise default to a hospital name.
        employer = p2  # fallback
        import re as _re
        for fact in s.extra_facts:
            _emp_match = _re.search(r'is_employee_of\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)', fact)
            if _emp_match and _emp_match.group(1) == p1:
                employer = _emp_match.group(2)
                break
        oracles.append(f'believes_unlawful_conduct("{p1}","{employer}").'  )
    if s.is_incident_to_use:
        oracles.append(f'is_incident_to_use("{p1}","{p2}","{q}","{m}","{t}","{u}").')
    if s.is_reply_to_request:
        oracles.append(f'is_reply_to_request("{p1}","{p2}","{q}","{m}","{t}","{u}").')
    if s.secretary_investigation_authorized:
        oracles.append(f'secretary_investigation_authorized("{p1}","{p2}","{q}","{m}","{t}","{u}").')
    if s.abuse_exception:
        oracles.append(f'abuse_exception("{p2}","{q}").')
    if s.minor_acts_as_individual:
        oracles.append(f'minor_acts_as_individual("{p2}","{q}").')
    if s.permitted_by_other_law:
        oracles.append(f'permitted_by_other_law("{p1}","{p2}","{q}","{t}","{u}").')
    if s.prohibited_by_other_law:
        oracles.append(f'prohibited_by_other_law("{p1}","{p2}","{q}","{t}","{u}").')
    if oracles:
        lines += ["// --- Oracle predicates ---"] + oracles + [""]

    if s.extra_facts:
        lines += ["// --- Extra facts ---"] + s.extra_facts + [""]

    lines += [
        "// --- Disclosure query ---",
        f'disclosure_attempted("{p1}","{p2}","{q}","{m}","{t}","{u}").',
    ]
    return "\n".join(lines) + "\n"


def _extract_citations(tree: str) -> list:
    patterns = [
        r'164\.\d+(?:\([a-z0-9]+\))*',             # HIPAA  §164.xxx
        r'Art\.?\s*\d+(?:\(\d+\))?(?:\([a-z]\))?', # GDPR   Art.6(1)(a)
        r'§\s*313\.\d+(?:\([a-z0-9]+\))*',          # GLBA   §313.x
        r'§\s*1798\.\d+(?:\([a-z0-9]+\))*',          # CCPA   §1798.x
        r'§\s*31[0-9]\.\d+(?:\([a-z0-9]+\))*',       # COPPA  §312.x
        r'§?\s*(?:80[0-9]|30[234]|40[24])\b',        # SOX    §302/404/802
    ]
    found = set()
    for pat in patterns:
        found.update(re.findall(pat, tree, re.IGNORECASE))
    return sorted(found)


# ─────────────────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────────────────

# Sections that may or may not exist in the project dir
OPTIONAL_SECTIONS = [
    "hipaa_164_508.dl", "hipaa_164_510.dl",
    "hipaa_164_512.dl", "hipaa_164_514.dl", "hipaa_164_524.dl",
]

REQUIRED_SECTIONS = [
    "hipaa_types.dl", "hipaa_hierarchies.dl", "hipaa_macros.dl",
    "hipaa_stubs.dl", "hipaa_164_506.dl", "hipaa_164_502.dl", "hipaa_top.dl",
]


class HIPAAEngine:
    """
    Thin Python wrapper around the Souffle HIPAA compliance checker.

    Parameters
    ----------
    souffle_project_dir : str
        ABSOLUTE path to the datalog_engine/ directory containing hipaa_*.dl files.
        Example: "/Users/priscilladanso/COMPLIANCEGPT/datalog_engine"
    souffle_binary : str | None
        Path to souffle. If None, auto-detects from PATH and common locations.
    timeout : int
        Max seconds for souffle to run (default 30).
    """

    def __init__(
        self,
        souffle_project_dir: str,
        souffle_binary: Optional[str] = None,
        timeout: int = 30,
    ):
        self.project_dir = os.path.abspath(souffle_project_dir)

        if not os.path.isdir(self.project_dir):
            raise ValueError(
                f"souffle_project_dir does not exist: {self.project_dir}\n"
                f"Set it to the absolute path of your datalog_engine/ folder."
            )

        # Auto-detect souffle if not specified
        if souffle_binary:
            self.souffle_binary = souffle_binary
        else:
            try:
                self.souffle_binary = find_souffle()
            except RuntimeError as e:
                self.souffle_binary = None
                self._souffle_error = str(e)

        self.timeout = timeout

    def check(self, scenario: DatalogScenario) -> EngineResult:
        if not hasattr(self, 'souffle_binary') or self.souffle_binary is None:
            return EngineResult(
                verdict="ERROR",
                scenario=scenario,
                error_message=getattr(self, '_souffle_error', 'Souffle not found.'),
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            facts_text = scenario_to_datalog(scenario)
            facts_path = os.path.join(tmpdir, "hipaa_query_facts.dl")
            with open(facts_path, "w") as f:
                f.write(facts_text)

            main_text = self._build_main(facts_path)
            main_path = os.path.join(tmpdir, "hipaa_query_main.dl")
            with open(main_path, "w") as f:
                f.write(main_text)

            output_dir = os.path.join(tmpdir, "output")
            os.makedirs(output_dir, exist_ok=True)

            try:
                proc = subprocess.run(
                    [self.souffle_binary, "-D", output_dir, main_path],
                    capture_output=True, text=True,
                    timeout=self.timeout,
                    cwd=self.project_dir,
                )
            except subprocess.TimeoutExpired:
                return EngineResult(
                    verdict="ERROR", scenario=scenario,
                    error_message=f"Souffle timed out after {self.timeout}s.",
                    generated_facts=facts_text,
                )

            if proc.returncode != 0:
                # Warnings (no rules/facts) produce returncode=1 but CSVs are written.
                # Only treat as hard error if CSVs are missing or stderr has "Error:"
                out_dir_path = os.path.join(tmpdir, "output")
                csvs_exist = (
                    os.path.exists(os.path.join(out_dir_path, "is_disclosure_allowed.csv")) or
                    os.path.exists(os.path.join(out_dir_path, "is_disclosure_denied.csv"))
                )
                if not csvs_exist or "Error:" in proc.stderr:
                    return EngineResult(
                        verdict="ERROR", scenario=scenario,
                        error_message=f"Souffle error:\n{proc.stderr.strip()[:600]}",
                        generated_facts=facts_text,
                    )
                # else: warnings only, CSVs exist — continue

            allowed = self._read_csv(os.path.join(output_dir, "is_disclosure_allowed.csv"))
            denied  = self._read_csv(os.path.join(output_dir, "is_disclosure_denied.csv"))
            return self._build_result(scenario, allowed, denied, facts_text)

    def _build_main(self, facts_path: str) -> str:
        """
        Build the main include file for a query run.

        CRITICAL: We include only the rule files (.dl logic), NOT hipaa_facts.dl
        or hipaa_main.dl. Including hipaa_main.dl would pull in hipaa_facts.dl
        which contains test scenarios — their results would contaminate the
        is_disclosure_allowed.csv output and cause false ALLOWED verdicts.

        We include only: types → hierarchies → macros → stubs → rule sections
        → top-level → query facts (just the one scenario being checked).
        """
        proj = self.project_dir
        lines = [
            f'#include "{proj}/hipaa_types.dl"',
            f'#include "{proj}/hipaa_hierarchies.dl"',
            f'#include "{proj}/hipaa_macros.dl"',
            f'#include "{proj}/hipaa_stubs.dl"',
            f'#include "{proj}/hipaa_164_506.dl"',
        ]
        # Optional extended sections — include if they exist
        for sec in OPTIONAL_SECTIONS:
            full = os.path.join(proj, sec)
            if os.path.exists(full):
                lines.append(f'#include "{full}"')
        lines += [
            f'#include "{proj}/hipaa_164_502.dl"',
            f'#include "{proj}/hipaa_top.dl"',
            # Query facts LAST — only the scenario being checked, no test data
            f'#include "{facts_path}"',
        ]
        # Explicitly DO NOT include:
        #   hipaa_main.dl   (includes hipaa_facts.dl)
        #   hipaa_facts.dl  (test scenarios that would contaminate results)
        return "\n".join(lines) + "\n"

    def _read_csv(self, path: str) -> list:
        if not os.path.exists(path):
            return []
        with open(path, newline="") as f:
            return list(csv.reader(f, delimiter="\t"))

    def _build_result(self, scenario, allowed, denied, facts_text) -> EngineResult:
        """
        Build EngineResult by filtering CSV rows to ONLY the query tuple.

        CRITICAL FIX: We must filter is_disclosure_allowed.csv rows to match
        the exact (p1, p2, q, m, t, u) tuple of the attempted disclosure.
        Without this filter, any ALLOWED row in the CSV — even from leftover
        test scenarios — would be incorrectly reported as ALLOWED for our query.

        CSV column order: p1, p2, q, m, t, u, explanation_tree
        """
        p1 = scenario.sender
        p2 = scenario.receiver
        q  = scenario.subject
        m  = scenario.message_id
        t  = scenario.attribute
        u  = scenario.purpose

        # Filter allowed rows to the exact query tuple
        matching_allowed = [
            row for row in allowed
            if len(row) >= 6
            and row[0] == p1
            and row[1] == p2
            and row[2] == q
            and row[3] == m
            and row[4] == t
            and row[5] == u
        ]

        # Filter denied rows to the exact query tuple
        matching_denied = [
            row for row in denied
            if len(row) >= 6
            and row[0] == p1
            and row[1] == p2
            and row[2] == q
            and row[3] == m
            and row[4] == t
            and row[5] == u
        ]

        if matching_allowed:
            expl = matching_allowed[0][6] if len(matching_allowed[0]) > 6 else ""
            return EngineResult(
                verdict="ALLOWED", scenario=scenario,
                explanation_tree=expl, citations=_extract_citations(expl),
                raw_allowed_rows=matching_allowed, raw_denied_rows=matching_denied,
                generated_facts=facts_text,
            )
        elif matching_denied:
            return EngineResult(
                verdict="DENIED", scenario=scenario,
                raw_denied_rows=matching_denied, generated_facts=facts_text,
            )
        else:
            # Neither matched — the disclosure_attempted fact wasn't in any output
            # This means a string constant mismatch or compilation issue
            # Show what was in the CSV to help debug
            debug_info = ""
            if allowed:
                sample = allowed[0]
                debug_info = (
                    f"\nQuery tuple: ({p1}, {p2}, {q}, {m}, {t}, {u})"
                    f"\nFirst allowed row: ({', '.join(sample[:6])})"
                    f"\nThese don't match — check role/attribute/purpose strings."
                )
            return EngineResult(
                verdict="UNKNOWN", scenario=scenario,
                error_message=(
                    "Disclosure not found in Souffle output. "
                    "Possible string constant mismatch."
                    + debug_info
                ),
                generated_facts=facts_text,
            )
