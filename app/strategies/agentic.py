"""
strategies/agentic.py — Strategy 4: Multi-agent pipeline.
Routes ALL API calls through ModelClient. No hardcoded Anthropic. temperature=0.0.

Default agent flow: A(extract) → B(map sections) → C(validate) → Souffle → [D(fix UNKNOWN)] → E(explain)

Optional: pass use_formal_extractor=True to replace Agents A→C with LLM1Extractor,
which uses the full AGENT_PROMPT.md system prompt (same as the formal strategy).
This is better for larger models that can follow complex instructions; the default
lightweight Agents A/B/C are better for small local models.
"""

import os, re, json, time, csv as csv_mod, subprocess
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from datetime import datetime
import uuid

try:
    from connector.model_client import ModelClient
    from connector.settings import get_settings
    from connector import config
    from connector.hipaa_engine import (
        DatalogScenario, EngineResult, scenario_to_datalog,
        find_souffle, _extract_citations,
    )
    from connector.llm1_extractor import LLM1Extractor
    from connector.llm2_explainer import LLM2Explainer
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from connector.model_client import ModelClient
    from connector.settings import get_settings
    from connector import config
    from connector.hipaa_engine import (
        DatalogScenario, EngineResult, scenario_to_datalog,
        find_souffle, _extract_citations,
    )
    from connector.llm1_extractor import LLM1Extractor
    from connector.llm2_explainer import LLM2Explainer

OPTIONAL_SECTIONS = [
    "hipaa_164_508.dl",
    "hipaa_164_510.dl",
    "hipaa_164_512.dl",
    "hipaa_164_514.dl",
    "hipaa_164_524.dl",
]


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class AgentTrace:
    agent:         str
    input_summary: str
    output_summary:str
    latency:       float
    success:       bool
    notes:         str = ""


@dataclass
class AgenticResult:
    strategy:         str  = "agentic"
    question:         str  = ""
    run_id:           str  = ""
    run_dir:          str  = ""
    verdict:          str  = ""
    answer:           str  = ""
    citations:        list = field(default_factory=list)
    explanation_tree: str  = ""
    scenario_json:    str  = ""
    generated_facts:  str  = ""
    traces:           list = field(default_factory=list)
    retry_count:      int  = 0
    latency_seconds:  float= 0.0
    error:            str  = ""
    model:            str  = ""
    provider:         str  = ""
    llm_raw:          str  = ""


# ── Agent prompts ─────────────────────────────────────────────────────────────

AGENT_A = """Extract the compliance scenario from the question. Output ONLY JSON.
{"sender":"","sender_role":"","receiver":"","receiver_role":"","subject":"",
"subject_category":"adult","attribute":"","purpose":"","notes":""}
Use role, attribute, and purpose values appropriate to the regulation being evaluated.
For HIPAA — roles: doctor,nurse,hospital,covered-entity,business-associate,patient,etc.
For GDPR — roles: controller,processor,data-subject,etc.
For GLBA — roles: financial-institution,consumer,service-provider,etc.
For CCPA — roles: business,service-provider,california-consumer,etc.
For COPPA — roles: operator,child,parent,third-party,etc.
For SOX  — roles: public-issuer,ceo,cfo,registered-auditor,etc.
CRITICAL — sender/receiver direction:
  sender = the party RELEASING or DISCLOSING the PHI/data (not the one asking the question).
  receiver = the party RECEIVING the PHI/data.
  When a patient asks to see/access their own records: sender=covered-entity (hospital/lab/provider), receiver=patient.
  When a doctor shares records with a specialist: sender=doctor, receiver=specialist."""

AGENT_B = """Identify the most relevant regulatory sections for this scenario. Output ONLY JSON.
{"primary_sections":["164.502"],"likely_permitted":true,
"key_conditions":[],"flags":[],"reasoning":""}
For HIPAA: 164.502,164.506,164.508,164.510,164.512,164.514,164.524
For GDPR: Art.6,Art.9,Art.17
For GLBA: §313.14
For CCPA: §1798.100,§1798.120
For COPPA: §312.4,§312.5
For SOX: §302,§404"""

AGENT_C = """You are a Souffle Datalog type-checker. Output the COMPLETE validated scenario JSON.
Correct any invalid string constants to the nearest valid value.
Output ONLY this JSON (no prose):
{"sender":"","sender_role":"","receiver":"","receiver_role":"","subject":"",
"subject_category":"adult","attribute":"","purpose":"","message_id":"msg_001",
"same_org":false,"is_business_associate":false,"is_guardian_of_subject":false,
"has_authority_to_act":false,"provider_patient":false,
"believes_minimum_necessary":false,"obtained_consent_506b":false,
"satisfactory_assurances":false,"obtained_authorization_164_508":false,
"believes_unlawful_conduct":false,"believes_victim_of_crime":false,
"is_incident_to_use":false,"is_reply_to_request":false,
"secretary_investigation_authorized":false,"abuse_exception":false,
"minor_acts_as_individual":false,"permitted_by_other_law":false,
"prohibited_by_other_law":false,"extra_facts":[]}"""

AGENT_D = """The Souffle engine returned an unexpected verdict. Fix the scenario JSON.
Common errors:
  'physician'→'doctor', 'test-results'→'lab-results', 'healthcare'→'healthcare-operations'
  patient accessing own records: sender=covered-entity, receiver=patient, subject must equal receiver
  sender/receiver direction: sender = the party RELEASING PHI; receiver = the party RECEIVING it.
  If sender and receiver look swapped (e.g. patient as sender, provider as receiver for an access request), flip them.
Output ONLY the corrected JSON (same schema as before)."""


# ── Strategy ──────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Shared postprocessing (mirrors llm1_extractor._postprocess)
# ─────────────────────────────────────────────────────────────────────────────

_ROLE_DEFAULT_ID = {
    "patient": "patient_a", "individual": "patient_a",
    "hospital": "hospital_a", "provider": "the_provider",
    "covered-entity": "the_ce", "doctor": "doctor_a",
    "nurse": "nurse_a", "pharmacist": "pharmacist_a",
    "psychiatrist": "psychiatrist_a", "lab-technician": "lab_a",
    "health-plan": "plan_a", "health-insurance-issuer": "insurer_a",
    "HMO": "hmo_a", "group-health-plan": "ghp_a",
    "clearinghouse": "clearinghouse_a",
    "billing-company": "billing_a", "cloud-storage": "cloud_a",
    "transcription-service": "transcription_a",
    "business-associate": "ba_a", "covered-entity": "ce_a",
    "oversight-agency": "agency_a",
    "public-health-authority": "pha_a",
    "law-enforcement-official": "leo_a",
    "parent": "parent_a", "legal-guardian": "guardian_a",
}


_ALL_ROLES = set(_ROLE_DEFAULT_ID.keys())


def _sanitize_id(val: str, role: str, fallback: str) -> str:
    """Return a valid Souffle principal identifier.

    Rejects:
      - empty string
      - bare role name used as an ID  (e.g. sender="patient" when sender_role="patient")
      - multi-word descriptions       (e.g. "request for medical records")
    and replaces with a role-derived default.
    """
    if not val:
        return _ROLE_DEFAULT_ID.get(role, fallback)
    # If the model used the role name itself as the entity ID, replace it
    if val.lower() in _ALL_ROLES:
        return _ROLE_DEFAULT_ID.get(role, fallback)
    # Multi-word values are descriptive text, not identifiers
    if " " in val:
        return _ROLE_DEFAULT_ID.get(role, fallback)
    return val


def _fill_empty_ids(data: dict) -> dict:
    """Sanitize principal identifiers.

    Small local models (e.g. gemma3:4b) produce broken IDs in three ways:
      1. Empty string   — ``{"sender": ""}``
      2. Role-as-ID     — ``{"sender": "patient", "sender_role": "patient"}``
      3. Descriptive    — ``{"subject": "request for medical records"}``

    All three cause Souffle tuple mismatches (DENIED / UNKNOWN on every row).
    Replace any broken ID with a role-derived default like ``"patient_a"``.
    """
    data["sender"]   = _sanitize_id(data.get("sender",   ""), data.get("sender_role",   ""), "entity_a")
    data["receiver"] = _sanitize_id(data.get("receiver", ""), data.get("receiver_role", ""), "entity_b")
    # Subject is always the patient — use "patient" as the role hint regardless of
    # receiver_role.  If we used receiver_role here (e.g. "third-party"), the fallback
    # would be "" → subject collapses to receiver, causing false ALLOWED verdicts via
    # the §164.502(a)(1)(i) "to the individual" pathway.
    subj = _sanitize_id(data.get("subject", ""), "patient", "")
    data["subject"] = subj or _ROLE_DEFAULT_ID.get("patient", "patient_a")
    return data


def _postprocess_scenario(data: dict, question: str) -> dict:
    """Apply safety guards to Agent C JSON output before sending to Souffle."""
    q = question.lower()

    # Fill empty principal IDs before any other guard runs
    data = _fill_empty_ids(data)

    # ── Normalize role strings (underscore → hyphen, aliases) ─────────────────
    _ROLE_NORM = {
        "covered_entity":       "covered-entity",
        "business_associate":   "business-associate",
        "health_plan":          "health-plan",
        "law_enforcement":      "law-enforcement-official",
        "law-enforcement":      "law-enforcement-official",
        "public_health":        "public-health-authority",
        "oversight_agency":     "oversight-agency",
        "legal_guardian":       "legal-guardian",
        "personal_representative": "personal-representative",
        "lab_technician":       "lab-technician",
    }
    for field in ("sender_role", "receiver_role"):
        val = data.get(field, "")
        if val in _ROLE_NORM:
            data[field] = _ROLE_NORM[val]

    # Sanitize extra_facts — strip invalid Souffle syntax
    try:
        from connector.llm1_extractor import _sanitize_extra_facts
        if "extra_facts" in data:
            data["extra_facts"] = _sanitize_extra_facts(data.get("extra_facts", []))
    except Exception:
        SAFE = ("activerole(","belongstorole(","organization_member(","is_employee_of(",
                "is_business_associate_of(","is_guardian(","has_authority_to_act(",
                "provider_of(","inrelationship(","pertains_to(","participates_in_ohca(",
                "msg_contains(","believes_minimum_necessary(","obtained_consent_506b(",
                "satisfactory_assurances(","ba_contract_permits(","believes_unlawful_conduct(",
                "is_incident_to_use(","is_reply_to_request(","abuse_exception(",
                "professional_judgment_best_interest_510b3(","is_family_member(",
                "permitted_by_other_law(","obtained_authorization_164_508(",
                "is_access_request(","is_in_designated_record_set(",
                "is_required_by_law(","is_authorized_by_law_for_purpose(",)
        data["extra_facts"] = [
            f for f in data.get("extra_facts",[])
            if isinstance(f,str) and f.strip().endswith('.')
               and any(f.strip().startswith(p) for p in SAFE)
        ]

    # ── Normalize invalid attribute strings ──────────────────────────────────
    # Agent C (and small models) often output plural or underscore variants.
    # Map common misspellings to the nearest valid hipaa_hierarchies constant.
    _VALID_PHI = {
        "psychotherapy-notes","genetic-info","substance-abuse-records","hiv-status",
        "blood-test-results","diagnosis","prescription","medical-record","billing-record",
        "lab-results","treatment-plan","patient-name","patient-location","patient-condition",
        "religious-affiliation","phi","dii","directory-information",
        "workplace-injury-findings","medical-surveillance-findings",
        "name-and-address","date-and-place-of-birth","social-security-number",
    }
    _ATTR_MAP = {
        "medical_records":          "medical-record",
        "medical_record":           "medical-record",
        "medical records":          "medical-record",
        "medical record":           "medical-record",
        "health-record":            "medical-record",
        "health_record":            "medical-record",
        "access_to_own_records":    "medical-record",
        "access_to_records":        "medical-record",
        "patient_records":          "medical-record",
        "health_information":       "medical-record",
        "health-information":       "medical-record",
        "protected_health_information": "medical-record",
        "phi":                      "medical-record",
        "lab_results":              "lab-results",
        "lab results":              "lab-results",
        "lab-result":               "lab-results",
        "test-results":             "lab-results",
        "test_results":             "lab-results",
        "laboratory-results":       "lab-results",
        "billing_record":           "billing-record",
        "billing records":          "billing-record",
        "prescriptions":            "prescription",
        "diagnoses":                "diagnosis",
        "psychotherapy_notes":      "psychotherapy-notes",
        "psychotherapy notes":      "psychotherapy-notes",
        "treatment_plan":           "treatment-plan",
        "patient_name":             "patient-name",
    }
    attr = data.get("attribute", "")
    if attr:
        attr_lc = attr.lower()
        if attr_lc != attr:
            data["attribute"] = attr_lc   # normalize case first (e.g. "HIV-status" → "hiv-status")
            attr = attr_lc
        if attr in _ATTR_MAP:
            data["attribute"] = _ATTR_MAP[attr]
        elif attr not in _VALID_PHI:
            # Unknown attribute — infer from question keywords
            if any(kw in q for kw in ("lab result", "lab test", "blood test", "test result")):
                data["attribute"] = "lab-results"
            elif any(kw in q for kw in ("billing", "invoice", "payment record")):
                data["attribute"] = "billing-record"
            elif any(kw in q for kw in ("psychotherapy", "therapy notes", "mental health note")):
                data["attribute"] = "psychotherapy-notes"
            else:
                data["attribute"] = "medical-record"  # safest default for patient records

    # ── Normalize invalid purpose strings ────────────────────────────────────
    # Small models sometimes output "authorization", "access", "administrative"
    # etc. which are not valid Souffle constants.  Map them to the closest valid
    # purpose so the engine can at least attempt to evaluate the scenario.
    _PURPOSE_MAP = {
        "health-care-operations":  "healthcare-operations",
        "access":                  "healthcare-operations",
        "authorization":           "healthcare-operations",
        "administrative":          "healthcare-operations",
        "operational":             "healthcare-operations",
        "care":                    "treatment",
        "medical-care":            "treatment",
        "follow-up":               "treatment",
        "medication":              "administer-medication",
        "billing-and-payment":     "billing",
        "insurance":               "claims-processing",
        "law-enforcement":         "compliance-investigation",
        "patient_access":          "healthcare-operations",
        "patient-access":          "healthcare-operations",
        "record-access":           "healthcare-operations",
        "individual-access":       "healthcare-operations",
    }
    purp = data.get("purpose", "")
    if purp and purp not in {
        "treatment","surgery","administer-medication","referral","consultation",
        "emergency-treatment","payment","billing","claims-processing",
        "eligibility-determination","reimbursement","healthcare-operations",
        "quality-assessment","case-management","care-coordination","fraud-detection",
        "compliance-audit","training-programs","marketing","research",
        "create-deidentified-info","compliance-investigation","report-unlawful-conduct",
        "determine-legal-options","directory",
    }:
        # Only map if we have an explicit mapping — unknown purposes stay as-is.
        # Leaving an unmapped purpose in the facts lets Soufflé's CWA produce DENIED
        # rather than opening false ALLOWED pathways via "healthcare-operations".
        mapped = _PURPOSE_MAP.get(purp.lower())
        if mapped:
            data["purpose"] = mapped

    # Fix wrong direction: patient/individual→provider must be provider→patient
    _PATIENT_ROLES    = ("patient", "individual", "parent", "legal-guardian")
    _PROVIDER_ROLES   = ("hospital","provider","covered-entity","doctor","nurse",
                         "pharmacist","lab-technician","psychiatrist","clearinghouse")
    if (data.get("receiver_role") in _PROVIDER_ROLES
            and data.get("sender_role") in _PATIENT_ROLES):
        data["sender"],      data["receiver"]      = data["receiver"],      data["sender"]
        data["sender_role"], data["receiver_role"]  = data["receiver_role"], data["sender_role"]

    # ── Guard: patient self-access (§164.524) ─────────────────────────────────
    # When a patient is accessing their OWN records, the engine needs the
    # is_access_request and is_in_designated_record_set oracle predicates.
    # Small models almost never add these — apply them from the question context.
    _self_access_kws = (
        "my record", "my medical record", "my lab result", "my health record",
        "my information", "my chart", "my file", "my data",
        "access my", "copy of my", "patient portal", "see my", "get my",
        "right to access", "view my",
    )
    if (data.get("receiver_role") in ("patient", "individual")
            and data.get("sender_role") in ("hospital","provider","covered-entity","doctor","nurse")
            and any(kw in q for kw in _self_access_kws)):
        recv = data["receiver"]
        send = data["sender"]
        attr = data.get("attribute", "medical-record")
        data["subject"] = recv   # patient is both subject and receiver
        existing = list(data.get("extra_facts", []))
        if not any("is_access_request" in f for f in existing):
            existing.append(f'is_access_request("{recv}","{send}","{recv}","{attr}").')
        if not any("is_in_designated_record_set" in f for f in existing):
            existing.append(f'is_in_designated_record_set("{send}","{recv}","{attr}").')
        data["extra_facts"] = existing

    # Marketing guard
    if data.get("purpose") == "marketing" or "marketing" in q:
        data["purpose"]               = "marketing"
        data["same_org"]              = False
        data["is_business_associate"] = False
        if not any(w in q for w in ["authorized","authorised","consent","signed"]):
            data["obtained_authorization_164_508"] = False

    # Abuse/mandatory reporting guard
    if any(w in q for w in ["child abuse","elder abuse","mandatory report","report abuse",
                             "suspected abuse","child protective"]):
        data["abuse_exception"]           = False
        data["believes_unlawful_conduct"] = False
        data["permitted_by_other_law"]    = True
        existing = list(data.get("extra_facts",[]))
        sender = data.get("sender","nurse_a")
        if not any("is_employee_of" in f for f in existing):
            base = sender.split("_")[0]
            employer = f"{base}_hospital" if base != sender else "hospital_a"
            existing += [f'is_employee_of("{sender}","{employer}").', f'activerole("{employer}","hospital").']
            data["extra_facts"] = existing

    return data


class AgenticStrategy:
    MAX_RETRIES = 2

    def __init__(self, api_key=None, runs_dir=None, use_formal_extractor: bool = False):
        """
        Parameters
        ----------
        use_formal_extractor : bool
            When True, replace Agents A/B/C with LLM1Extractor (AGENT_PROMPT.md).
            This gives the full formal extraction pipeline as the agentic first step.
            Best for larger API models (Anthropic, OpenAI, large Ollama).
            Default False uses the lightweight Agent A/B/C prompts, better for
            small local models like gemma3:4b.
        """
        s = get_settings()
        self._provider = s["llm1_provider"]
        self._model    = s["llm1_model"]
        self._api_key  = api_key
        self._use_formal_extractor = use_formal_extractor
        self._extractor = LLM1Extractor(api_key=api_key) if use_formal_extractor else None
        self.explainer = LLM2Explainer(api_key=api_key)

        project_root   = Path(config.DATALOG_ENGINE_DIR).parent
        self.runs_dir  = runs_dir or str(project_root / "runs")
        os.makedirs(self.runs_dir, exist_ok=True)

        try:    self.souffle_binary = find_souffle()
        except RuntimeError as e: self.souffle_binary=None; self._souffle_err=str(e)

    def _call(self, system: str, user: str) -> tuple[str, float, bool]:
        """Call the LLM via ModelClient. Returns (text, latency, success)."""
        t0 = time.time()
        try:
            # Use JSON mode for Ollama so the model is forced to return valid JSON
            # even with short/complex prompts that might otherwise produce prose.
            # Only pass response_format when non-None to avoid kwarg errors on any
            # ModelClient version that doesn't support the parameter.
            mc = ModelClient(provider=self._provider, model=self._model, api_key=self._api_key)
            if self._provider == "ollama":
                text = mc.complete(system=system, user=user, max_tokens=800, response_format="json")
            else:
                text = mc.complete(system=system, user=user, max_tokens=800)
            text = re.sub(r'^```(?:json)?\s*', '', text.strip())
            text = re.sub(r'\s*```$', '', text)
            json.loads(text)  # validate JSON
            return text, round(time.time()-t0, 2), True
        except Exception as e:
            return str(e), round(time.time()-t0, 2), False

    def run(self, question: str, progress_callback=None) -> AgenticResult:
        t0 = time.time()
        run_id  = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        run_dir = os.path.join(self.runs_dir, f"agentic_run_{run_id}")
        os.makedirs(os.path.join(run_dir, "output"), exist_ok=True)

        def _cb(msg: str):
            if progress_callback:
                progress_callback(msg)

        traces: list[AgentTrace] = []
        result = AgenticResult(question=question, run_id=run_id, run_dir=run_dir,
                               model=self._model, provider=self._provider)

        def trace(agent, inp, out, lat, ok, notes=""):
            traces.append(AgentTrace(agent=agent, input_summary=inp[:120],
                                     output_summary=out[:120], latency=lat,
                                     success=ok, notes=notes))

        # ── Extraction: LLM1Extractor (AGENT_PROMPT.md) or Agents A/B/C ────────
        if self._use_formal_extractor:
            _cb("Step 1/5 — LLM1Extractor: sending question for full fact extraction")
            t_ext = time.time()
            try:
                scenario_obj, scenario_json = self._extractor.extract(question)
                lat_ext = round(time.time() - t_ext, 2)
                trace("LLM1Extractor (AGENT_PROMPT.md)", question[:80],
                      scenario_json[:80], lat_ext, True,
                      notes=f"provider={self._extractor.provider}/{self._extractor.model}")
                _cb(f"Step 1/5 ✓ LLM1 extracted scenario ({lat_ext}s)")
                # Save as agent_c.json for consistency
                try:
                    with open(os.path.join(run_dir, "agent_c.json"), "w") as f:
                        json.dump(json.loads(scenario_json), f, indent=2)
                except Exception:
                    pass
            except Exception as e:
                lat_ext = round(time.time() - t_ext, 2)
                trace("LLM1Extractor (AGENT_PROMPT.md)", question[:80],
                      str(e)[:80], lat_ext, False)
                _cb(f"Step 1/5 — LLM1 extraction failed: {e}")
                result.verdict = "ERROR"
                result.error   = f"LLM1Extractor: {e}"
                result.traces  = traces
                result.latency_seconds = round(time.time() - t0, 2)
                return result

            # Skip Souffle+retry loop — go straight to engine with scenario_obj
            current_json = scenario_json
            _cb("Step 2/5 — Running Soufflé formal engine")
            engine_result = self._run_souffle(scenario_obj, run_dir)
            _cb(f"Step 2/5 ✓ Soufflé verdict: {engine_result.verdict}")

        else:
            # ── Agent A ───────────────────────────────────────────────────────
            _cb("Step 1/5 — Agent A: extracting entities from question")
            entity_json, lat, ok = self._call(AGENT_A, question)
            trace("Agent A — Entity Extractor", question[:80], entity_json[:80], lat, ok)
            if not ok:
                _cb(f"Step 1/5 — Agent A failed: {entity_json[:80]}")
                result.verdict="ERROR"; result.error=f"Agent A: {entity_json}"
                result.traces=traces; result.latency_seconds=round(time.time()-t0,2); return result
            _cb(f"Step 1/5 ✓ Agent A complete ({lat}s)")

            # ── Agent B ───────────────────────────────────────────────────────
            _cb("Step 2/5 — Agent B: mapping relevant regulatory sections")
            relev_json, lat, ok = self._call(AGENT_B, f"Q: {question}\nEntities: {entity_json}")
            trace("Agent B — Section Mapper", entity_json[:80], relev_json[:80], lat, ok)
            _cb(f"Step 2/5 ✓ Agent B complete ({lat}s)")

            # ── Agent C ───────────────────────────────────────────────────────
            _cb("Step 3/5 — Agent C: validating and converting to Datalog facts")
            scenario_json, lat, ok = self._call(AGENT_C, f"Q: {question}\nA output: {entity_json}")
            trace("Agent C — Facts Validator", entity_json[:80], scenario_json[:80], lat, ok)
            if not ok:
                _cb(f"Step 3/5 — Agent C failed: {scenario_json[:80]}")
                result.verdict="ERROR"; result.error=f"Agent C: {scenario_json}"
                result.traces=traces; result.latency_seconds=round(time.time()-t0,2); return result
            _cb(f"Step 3/5 ✓ Agent C complete — facts ready ({lat}s)")

            result.llm_raw = scenario_json   # raw Agent C output before postprocessing

            # Save agent outputs
            for fname, data in [("agent_a.json",entity_json),("agent_b.json",relev_json),("agent_c.json",scenario_json)]:
                try:
                    with open(os.path.join(run_dir, fname),"w") as f:
                        json.dump(json.loads(data), f, indent=2)
                except: pass

            # ── Postprocess Agent C output (same guards as LLM1 extractor) ────
            try:
                _cdata = json.loads(scenario_json)
                _cdata = _postprocess_scenario(_cdata, question)
                scenario_json = json.dumps(_cdata)
            except Exception:
                pass  # if JSON parse fails, proceed anyway — Souffle will error cleanly

        # ── Souffle + Agent D retry loop ──────────────────────────────────────
        # When use_formal_extractor=True, first Souffle run and current_json are
        # already set above; engine_result holds the initial verdict.
        # When use_formal_extractor=False, we still need to parse + run Souffle.
        if not self._use_formal_extractor:
            current_json  = scenario_json
            engine_result = None

        if not self._use_formal_extractor:
            _cb("Step 4/5 — Running Soufflé formal engine")

        for attempt in range(self.MAX_RETRIES + 1):
            # Skip first Souffle run when formal extractor already did it
            if self._use_formal_extractor and attempt == 0 and engine_result is not None:
                pass  # engine_result already populated above
            else:
                try:
                    data = json.loads(current_json)
                    # Fill missing required fields so small models don't raise TypeError
                    _DEFAULTS = {
                        "subject_category": "adult",
                        "sender":           "entity_a",
                        "sender_role":      "individual",
                        "receiver":         "entity_b",
                        "receiver_role":    "individual",
                        "subject":          "subject_a",
                        "attribute":        "medical-record",
                        "purpose":          "healthcare-operations",
                        "message_id":       "msg_001",
                    }
                    for _k, _v in _DEFAULTS.items():
                        if _k not in data or not data[_k]:
                            data[_k] = _v
                    scenario = DatalogScenario(**{k:v for k,v in data.items()
                                                  if k in DatalogScenario.__dataclass_fields__})
                except Exception as e:
                    result.verdict="ERROR"; result.error=f"JSON parse: {e}"; break

                engine_result = self._run_souffle(scenario, run_dir)

            if engine_result.verdict != "UNKNOWN" or attempt == self.MAX_RETRIES:
                break

            # Agent D — self-correct on UNKNOWN (string constant mismatch)
            _cb(f"Step 4/5 — Soufflé returned UNKNOWN — Agent D: self-correcting (retry {attempt+1})")
            d_in = (f"Q: {question}\nCurrent JSON:\n{current_json}\n"
                    f"Datalog facts:\n{engine_result.generated_facts}\n"
                    f"Souffle returned: UNKNOWN")
            fixed, lat, ok = self._call(AGENT_D, d_in)
            result.retry_count += 1
            trace(f"Agent D — Resolver (retry {result.retry_count})", d_in[:80], fixed[:80], lat, ok,
                  notes="" if ok else fixed[:100])
            if ok:
                current_json = fixed
                with open(os.path.join(run_dir, f"agent_d_retry{result.retry_count}.json"),"w") as f:
                    json.dump(json.loads(fixed), f, indent=2)

        if engine_result:
            result.verdict          = engine_result.verdict
            result.citations        = engine_result.citations
            result.explanation_tree = engine_result.explanation_tree
            result.generated_facts  = engine_result.generated_facts
            result.error            = engine_result.error_message
            _v = engine_result.verdict
            _cit = (", ".join(engine_result.citations)) if engine_result.citations else "—"
            _step = "2" if self._use_formal_extractor else "4"
            _cb(f"Step {_step}/5 ✓ Soufflé verdict: {_v}  citations: {_cit}")
        result.scenario_json = current_json

        # ── Agent E — Explain ─────────────────────────────────────────────────
        if engine_result:
            _cb("Step 5/5 — Agent E: generating explanation (LLM2)")
            t_e = time.time()
            try:
                result.answer = self.explainer.explain(question, engine_result)
                trace("Agent E — Explainer", f"verdict={result.verdict}", "answer generated",
                      round(time.time()-t_e,2), True)
                _cb(f"Step 5/5 ✓ Done — verdict: {result.verdict}  ({round(time.time()-t0,1)}s)")
            except Exception as e:
                trace("Agent E — Explainer","","",round(time.time()-t_e,2),False,str(e))
                _cb(f"Step 5/5 — Agent E failed: {e}")

        result.traces          = traces
        result.latency_seconds = round(time.time()-t0, 2)
        self._save_result(result, run_dir)
        return result

    def _run_souffle(self, scenario: DatalogScenario, run_dir: str) -> EngineResult:
        proj = config.DATALOG_ENGINE_DIR

        from strategies.formal import REGULATION_FILES
        regulation = get_settings().get("active_regulation", "hipaa")
        reg_cfg    = REGULATION_FILES.get(regulation, REGULATION_FILES["hipaa"])

        facts_text = scenario_to_datalog(scenario)
        # Strip HIPAA-specific predicates for non-HIPAA regulations
        from strategies.formal import FormalStrategy as _FS
        facts_text = _FS._adapt_facts(facts_text, regulation)
        facts_path = os.path.join(run_dir, f"{regulation}_query_facts.dl")
        with open(facts_path,"w") as f: f.write(facts_text)

        lines = []
        for f_name in reg_cfg["required"]:
            lines.append(f'#include "{proj}/{f_name}"')
        for f_name in reg_cfg["optional"]:
            full = os.path.join(proj, f_name)
            if os.path.exists(full): lines.append(f'#include "{full}"')
        for f_name in reg_cfg["final"]:
            lines.append(f'#include "{proj}/{f_name}"')
        lines.append(f'#include "{facts_path}"')
        main_path = os.path.join(run_dir, f"{regulation}_query_main.dl")
        with open(main_path,"w") as f: f.write("\n".join(lines)+"\n")

        output_dir = os.path.join(run_dir,"output")
        os.makedirs(output_dir, exist_ok=True)

        try:
            proc = subprocess.run(
                [self.souffle_binary,"-D",output_dir,main_path],
                capture_output=True, text=True,
                timeout=config.SOUFFLE_TIMEOUT_SECONDS,
                cwd=config.DATALOG_ENGINE_DIR,
            )
        except subprocess.TimeoutExpired:
            return EngineResult(verdict="ERROR",scenario=scenario,
                                error_message="Souffle timed out.",generated_facts=facts_text)

        with open(os.path.join(run_dir,"souffle.log"),"w") as f:
            f.write(f"rc={proc.returncode}\n{proc.stdout}\n{proc.stderr}")

        if proc.returncode != 0:
            _ac=os.path.join(output_dir,"is_disclosure_allowed.csv")
            _dc=os.path.join(output_dir,"is_disclosure_denied.csv")
            if not (os.path.exists(_ac) or os.path.exists(_dc)) or "Error:" in proc.stderr:
                return EngineResult(verdict="ERROR",scenario=scenario,
                                    error_message=proc.stderr[:400],generated_facts=facts_text)

        p1,p2,q = scenario.sender,scenario.receiver,scenario.subject
        m,t,u   = scenario.message_id,scenario.attribute,scenario.purpose

        def read_csv(path):
            if not os.path.exists(path): return []
            with open(path,newline="") as f:
                return [r for r in csv_mod.reader(f,delimiter="\t")
                        if len(r)>=6 and r[:6]==[p1,p2,q,m,t,u]]

        allowed = read_csv(os.path.join(output_dir,"is_disclosure_allowed.csv"))
        denied  = read_csv(os.path.join(output_dir,"is_disclosure_denied.csv"))

        if allowed:
            expl=allowed[0][6] if len(allowed[0])>6 else ""
            return EngineResult(verdict="ALLOWED",scenario=scenario,
                                explanation_tree=expl,citations=_extract_citations(expl),
                                raw_allowed_rows=allowed,generated_facts=facts_text)
        elif denied:
            return EngineResult(verdict="DENIED",scenario=scenario,
                                raw_denied_rows=denied,generated_facts=facts_text)
        else:
            debug=""
            all_rows=[]
            ap=os.path.join(output_dir,"is_disclosure_allowed.csv")
            if os.path.exists(ap):
                with open(ap,newline="") as f: all_rows=list(csv_mod.reader(f,delimiter="\t"))
            if all_rows: debug=f"\nQuery:({p1},{p2},{q},{m},{t},{u})\nFirst row:({','.join(all_rows[0][:6])})"
            return EngineResult(verdict="UNKNOWN",scenario=scenario,
                                error_message="No matching output."+debug,
                                generated_facts=facts_text)

    def _save_result(self, result, run_dir):
        meta={"run_id":result.run_id,"strategy":"agentic","question":result.question,
              "verdict":result.verdict,"model":result.model,"provider":result.provider,
              "citations":result.citations,"retry_count":result.retry_count,
              "latency_seconds":result.latency_seconds,
              "traces":[{"agent":t.agent,"latency":t.latency,"success":t.success,"notes":t.notes}
                        for t in result.traces],
              "timestamp":datetime.now().isoformat()}
        with open(os.path.join(run_dir,"result.json"),"w") as f:
            json.dump(meta,f,indent=2)