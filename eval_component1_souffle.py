#!/usr/bin/env python3
"""
eval_component1_souffle.py — Component 1: Soufflé engine isolation

Oracle pipeline: GoldCoin generate_characteristics dict → Claude Sonnet
(condensed role/attribute/purpose hierarchy prompt) → DatalogScenario
→ Soufflé engine → verdict.

Claude Sonnet IS used here, but only for a narrowly scoped mapping task
(structured dict → exact Soufflé constants) rather than the full LLM1
pipeline (unstructured NL narrative + AGENT_PROMPT.md). This isolates the
accuracy of the Soufflé formalisation from LLM1 extraction noise. The
accuracy gap between this script and eval_e2e.py quantifies LLM1's error
contribution to the end-to-end pipeline.

Per-row artifacts saved to data/eval_component1_artifacts/<row_id>/:
  hipaa_query_facts.dl   — generated Datalog facts
  output/                — Soufflé output CSVs (is_disclosure_allowed.csv, etc.)

Summary CSV: data/eval_component1.csv

Usage:
    python eval_component1_souffle.py
    python eval_component1_souffle.py --model anthropic/claude-sonnet-4-6
    python eval_component1_souffle.py --skip-existing --limit 10 --out data/c1.csv
"""

import argparse, ast, csv, json, os, re, sys, time, uuid
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from connector.dataset_loader import load_dataset
from connector.hipaa_engine import DatalogScenario
from connector.model_client import ModelClient
from connector.settings import get_settings

# ── Characteristics → DatalogScenario prompt ────────────────────────────────

_CHARS_SYSTEM = """\
Convert a GoldCoin HIPAA scenario's characteristics dict into a DatalogScenario JSON.
Use ONLY the exact Soufflé hierarchy constants listed below (pick the single closest match for each field).

sender_role / receiver_role — exact strings only:
  Individual clinical providers:
    psychiatrist | doctor | nurse | pharmacist | lab-technician | provider
  Covered entity types:
    covered-entity | health-insurance-issuer | HMO | group-health-plan | health-plan | clearinghouse | hospital
  Business associates:
    billing-company | cloud-storage | transcription-service | business-associate
  Oversight / government:
    oversight-agency | public-health-authority | law-enforcement-official |
    authorized-federal-official | DoS-official | DVA | component-of-DVA | component-of-DoS |
    government-authority | government-entity
  Personal representatives / other:
    parent | legal-guardian | loco-parentis | guardian-type | individual |
    clergy | coroner | medical-examiner | funeral-director |
    organ-procurement-organization | researcher | correctional-institution
  NOTE: use "individual" for patient/consumer; "law-enforcement-official" for police/FBI/DEA/detective;
        "government-entity" for generic government; "health-insurance-issuer" for insurer/payer.

attribute (PHI type being disclosed) — exact strings only:
  Sensitive: psychotherapy-notes | genetic-info | substance-abuse-records | hiv-status | blood-test-results
  Clinical:  diagnosis | prescription | medical-record | billing-record | lab-results | treatment-plan
  Identifiers: patient-name | patient-location | patient-condition | social-security-number |
               name-and-address | date-and-place-of-birth | date-and-time-of-treatment |
               date-and-time-of-death | ABO-blood-type-and-rh-factor | type-of-injury |
               distinguishing-physical-characteristics
  Special: suspected-perpetrator-info | workplace-injury-findings | medical-surveillance-findings |
           religious-affiliation | statistical-data | anonymized-record
  Aggregates: limited-data-set | demographic-info | healthcare-dates | phi | dii
  NOTE: use "medical-record" for general health/patient records; "phi" for unspecified health info;
        "psychotherapy-notes" for mental health/therapy notes; "genetic-info" for DNA/genetics.

purpose (reason for disclosure) — exact strings only:
  Treatment:   treatment | surgery | administer-medication | administer-blood-test |
               referral | consultation | emergency-treatment
  Payment:     payment | billing | claims-processing | eligibility-determination | reimbursement | collections
  Operations:  healthcare-operations | quality-assessment | quality-improvement | case-management |
               care-coordination | competency-assurance | fraud-detection | compliance-audit |
               business-planning | accreditation | training-programs
  Other:       marketing | research | create-deidentified-info | compliance-investigation |
               report-unlawful-conduct | determine-legal-options | directory | legal-defense
  §164.510:    notification-164-510b | assist-notification-164-510b
  Public health: disease-prevention-or-control | public-health-surveillance | public-health-investigation |
                 public-health-intervention | reports-of-child-abuse | reports-of-abuse |
                 fda-quality-safety-effectiveness | obligation-to-record-workplace-injury |
                 obligation-to-perform-medical-surveillance | public-health
  Oversight/judicial/LE: health-oversight | judicial-administrative-proceeding |
                         law-enforcement | law-enforcement-identification-or-location |
                         suspicious-death-notification | report-crime-on-premises | alert-law-enforcement-of-crime
  Decedent/organ/threat: identification-of-deceased | determining-cause-of-death |
                         funeral-director-duties | facilitate-organ-donation-transplantation |
                         lessen-health-threat | identify-apprehend
  National security/military: national-security-activities | provision-of-protective-services |
                               conduct-investigations-18USC871-and-879 | security-clearance-EO-10450-and-12698 |
                               determine-availability-for-foreign-service | determine-family-accompaniment-FSA
  Veterans/workers comp: eligibility-determination-for-veterans-benefits | provision-of-veterans-benefits |
                         workers-compensation
  Fundraising: fundraising
  NOTE: use "law-enforcement" for subpoenas/court orders/criminal investigations;
        "treatment" for care/medical; "healthcare-operations" for admin/operations.

subject_category: adult | unemancipated-minor | emancipated-minor | deceased | incapacitated

Infer boolean fields from the characteristics. When unsure, default to false.

Output ONLY a valid JSON object — no markdown fences, no extra text:
{
  "sender_role": "...",
  "receiver_role": "...",
  "attribute": "...",
  "purpose": "...",
  "subject_category": "adult",
  "same_org": false,
  "is_business_associate": false,
  "is_guardian_of_subject": false,
  "obtained_authorization_164_508": false
}
"""


def _map_characteristics(chars_raw: str, client: ModelClient) -> dict | None:
    """Call Claude to map a raw characteristics dict string to DatalogScenario fields."""
    try:
        chars = ast.literal_eval(chars_raw.strip())
    except Exception:
        chars = chars_raw

    user_msg = f"CHARACTERISTICS:\n{json.dumps(chars, indent=2) if isinstance(chars, dict) else chars_raw}"

    try:
        raw = client.complete(system=_CHARS_SYSTEM, user=user_msg, max_tokens=300)
        m = re.search(r'\{.*?\}', raw, re.DOTALL)
        return json.loads(m.group(0)) if m else json.loads(raw)
    except Exception as e:
        print(f"  [chars mapping error] {e}")
        return None


def _normalize_fields(fields: dict, question: str, chars_raw: str = "") -> dict:
    """Apply role/attribute/purpose normalization to catch model errors.

    Two-pass approach:
    1. Keyword override from the raw generate_characteristics string (catches cases
       where the model picks the wrong constant but the characteristics clearly indicate
       the right one — e.g. Purpose="Evidence in criminal case" → law-enforcement).
    2. llm1_extractor._postprocess() for full hierarchy normalization.
    """
    fields = dict(fields)

    # Pass 1 — keyword override from characteristics Purpose field
    if chars_raw:
        try:
            import ast as _ast
            chars = _ast.literal_eval(chars_raw.strip()) if chars_raw.strip().startswith("{") else {}
            raw_purpose = str(chars.get("Purpose", "")).lower()
            raw_recip   = str(chars.get("Recipient Role", "")).lower()
        except Exception:
            raw_purpose = chars_raw.lower()
            raw_recip   = ""

        _PURPOSE_KW = [
            (["criminal", "subpoena", "court order", "warrant", "law enforce",
              "evidence", "investigate", "prosecution", "judicial", "legal proceeding"],
             "law-enforcement"),
            (["public health", "disease", "epidem", "outbreak", "reportable"],
             "public-health-surveillance"),
            (["research", "irb", "study", "clinical trial"],
             "research"),
            (["marketing", "advertis", "promot"],
             "marketing"),
            (["treatment", "care", "surgery", "emergency"],
             "treatment"),
            (["payment", "billing", "reimburse", "insurance claim"],
             "billing"),
            (["oversight", "audit", "compliance", "accreditat"],
             "health-oversight"),
            (["organ donation", "transplant"],
             "facilitate-organ-donation-transplantation"),
            (["funeral", "deceased", "death", "coroner"],
             "funeral-director-duties"),
        ]
        for keywords, purpose_const in _PURPOSE_KW:
            if any(kw in raw_purpose for kw in keywords):
                fields["purpose"] = purpose_const
                break

        # Sender / Recipient Role keyword overrides
        _ROLE_KW = [
            (["law enforce", "police", "fbi", "dea", "detective", "investigat",
              "judicial", "court", "prosecutor"],
             "law-enforcement-official"),
            (["public health", "cdc", "health department"],
             "public-health-authority"),
            (["government", "federal", "state agency"],
             "government-entity"),
            (["researcher", "research institution", "irb"],
             "researcher"),
            (["coroner", "medical examiner"],
             "medical-examiner"),
            (["healthcare provider", "health care provider", "medical provider",
              "hospital", "clinic", "physician", "doctor", "provider"],
             "hospital"),
            (["health plan", "insur", "payer"],
             "health-plan"),
            (["business associate", "clearinghouse"],
             "business-associate"),
        ]
        raw_sender = str(chars.get("Sender Role", "") if isinstance(chars, dict) else "").lower()
        for role_fld, raw_role in [("receiver_role", raw_recip), ("sender_role", raw_sender)]:
            for keywords, role_const in _ROLE_KW:
                if any(kw in raw_role for kw in keywords):
                    fields[role_fld] = role_const
                    break

    # Pass 2 — LLM1Extractor._postprocess for full hierarchy normalization
    try:
        from connector.llm1_extractor import LLM1Extractor
        extractor = object.__new__(LLM1Extractor)
        extractor._prompt_path = "(component1-normalize)"
        fields = extractor._postprocess(fields, question)
    except Exception:
        pass

    # Upgrade generic covered-entity to hospital for treatment disclosures.
    # Treatment rules require is_health_care_provider; hospital satisfies this,
    # generic covered-entity does not.
    if fields.get("purpose") == "treatment":
        if fields.get("sender_role") == "covered-entity":
            fields["sender_role"] = "hospital"
        if fields.get("receiver_role") == "covered-entity":
            fields["receiver_role"] = "hospital"

    # For law-enforcement disclosures, a government-entity receiver is acting as
    # law enforcement. §164.512(f) requires is_law_enforcement(p2), which only
    # fires for law-enforcement-official — not government-entity.
    if fields.get("purpose") == "law-enforcement":
        if fields.get("receiver_role") == "government-entity":
            fields["receiver_role"] = "law-enforcement-official"

    # If receiver is a healthcare provider or the patient (individual),
    # judicial-administrative-proceeding is almost certainly wrong —
    # the disclosure was for treatment. §164.512(e) judicial disclosures
    # go to courts/attorneys, not to providers or individual patients.
    _PROVIDER_ROLES = (
        "hospital", "doctor", "nurse", "pharmacist", "psychiatrist",
        "covered-entity", "provider", "lab-technician",
    )
    if (fields.get("purpose") == "judicial-administrative-proceeding"
            and fields.get("receiver_role") in _PROVIDER_ROLES):
        fields["purpose"] = "treatment"
    if (fields.get("purpose") == "judicial-administrative-proceeding"
            and fields.get("receiver_role") == "individual"):
        fields["purpose"] = "treatment"

    return fields


def _build_scenario(fields: dict, row_idx: int, question: str = "", chars_raw: str = "") -> DatalogScenario:
    """Construct a DatalogScenario from mapped fields with normalization + safe defaults."""
    fields = _normalize_fields(fields, question, chars_raw)
    def _b(k): return str(fields.get(k, "false")).lower() in ("true", "1", "yes")

    p1 = f"sender_{row_idx}"
    q  = f"patient_{row_idx}"
    t  = fields.get("attribute", "medical-record")
    u  = fields.get("purpose", "treatment")

    # When receiver_role=individual the receiver IS the patient (self-disclosure).
    # Set p2 = q so §164.502(a)(1)(i) fires (requires p2 = q).
    receiver_role = fields.get("receiver_role", "individual")
    p2 = q if receiver_role == "individual" else f"receiver_{row_idx}"

    # Infer §164.512 oracle predicates from characteristics / question text.
    # Component 1 constructs the best-possible oracle; §164.512 sub-rules
    # require predicates absent from the 9-field DatalogScenario JSON, so we
    # infer them from the "In Reply To" field (highest signal) and free text.
    extra_facts: list = []
    combined = (chars_raw + " " + question).lower()
    in_reply_to = ""
    try:
        import ast as _a
        ch = _a.literal_eval(chars_raw.strip()) if chars_raw.strip().startswith("{") else {}
        in_reply_to = str(ch.get("In Reply To", "")).lower()
    except Exception:
        pass

    if u == "law-enforcement":
        if any(kw in in_reply_to + combined for kw in [
                "subpoena", "court order", "warrant", "grand jury", "pursuant to",
                "prosecutor", "prosecution", "court-ordered", "judicial order",
                "drug enforcement", "controlled substance", "criminal trial",
                "law enforcement request"]):
            extra_facts.append(
                f'in_compliance_with_court_order("{p1}","{p2}","{q}","{t}","{u}").'
            )
        elif any(kw in combined for kw in [
                "required by law", "mandatory report", "obligat", "statutory",
                "public health", "notifiable", "reportable disease"]):
            extra_facts.append(
                f'is_required_by_law("{p1}","{p2}","{q}","{t}","{u}").'
            )
        # No clear legal basis → no oracle predicate → engine returns DENIED (correct CWA)

    elif u == "judicial-administrative-proceeding":
        if any(kw in in_reply_to + combined for kw in ["court order", "court-ordered"]):
            extra_facts.append(
                f'has_court_order("{p1}","{p2}","{q}","{t}","{u}").'
            )
        elif any(kw in in_reply_to + combined for kw in ["subpoena", "discovery request"]):
            extra_facts.append(
                f'has_lawful_process_with_assurance("{p1}","{p2}","{q}","{t}","{u}").'
            )

    elif u == "lessen-health-threat":
        # §164.512(j)(1)(i): CE believes disclosure necessary to prevent serious/imminent threat.
        # Oracle predicates required by the rule — infer when purpose is lessen-health-threat.
        extra_facts.append(f'consistent_with_applicable_law("{p1}","{p2}","{q}","{t}","{u}").')
        extra_facts.append(f'believes_necessary_to_lessen_threat("{p1}","{p2}","{q}","{t}","{u}").')
        extra_facts.append(f'believes_can_lessen_threat("{p1}","{p2}","{u}").')

    elif u in ("health-oversight", "public-health-surveillance", "public-health-investigation",
               "public-health-intervention", "disease-prevention-or-control"):
        # §164.512(b)/(d): oversight/public-health authorities are authorized by law.
        # The rule requires is_authorized_by_law_for_purpose(p2, u) as an oracle predicate.
        extra_facts.append(f'is_authorized_by_law_for_purpose("{p2}","{u}").')

    return DatalogScenario(
        sender           = p1,
        sender_role      = fields.get("sender_role", "covered-entity"),
        receiver         = p2,
        receiver_role    = fields.get("receiver_role", "individual"),
        subject          = q,
        subject_category = fields.get("subject_category", "adult"),
        attribute        = t,
        purpose          = u,
        message_id       = f"msg_{row_idx:04d}",
        same_org                       = _b("same_org"),
        is_business_associate          = _b("is_business_associate"),
        is_guardian_of_subject         = _b("is_guardian_of_subject"),
        obtained_authorization_164_508 = _b("obtained_authorization_164_508"),
        extra_facts                    = extra_facts,
    )


def _norm_verdict(v: str) -> str:
    v = v.strip().upper()
    return "PERMITTED" if v in ("ALLOWED", "PERMITTED") else v


def _norm_gold(v: str) -> str:
    v = v.strip().lower()
    if v in ("permit", "permitted", "allowed", "yes"): return "PERMITTED"
    if v in ("forbid", "forbidden", "denied", "no"):   return "DENIED"
    return v.upper()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Component 1: Soufflé engine isolation (oracle facts)")
    parser.add_argument("--dataset", default="data/goldcoin.csv",
                        help="GoldCoin CSV path (default: data/goldcoin.csv)")
    parser.add_argument("--model", default=None,
                        help="Model for characteristics mapping: provider/model "
                             "(default: reads llm1_provider/llm1_model from settings)")
    parser.add_argument("--out", default="data/eval_component1.csv",
                        help="Output summary CSV (default: data/eval_component1.csv)")
    parser.add_argument("--artifacts-dir", default="data/eval_component1_artifacts",
                        help="Directory for per-row Soufflé artifacts")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to process")
    parser.add_argument("--offset", type=int, default=0,
                        help="Skip first N rows before applying --limit")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip rows whose artifact dir already exists")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="Seconds to sleep between rows (prevents Ollama timeouts on large models)")
    args = parser.parse_args()

    # ── Setup ──────────────────────────────────────────────────────────────────
    dataset_path = PROJECT_ROOT / args.dataset
    if not dataset_path.exists():
        print(f"ERROR: Dataset not found: {dataset_path}", file=sys.stderr); sys.exit(1)

    artifacts_base = PROJECT_ROOT / args.artifacts_dir
    artifacts_base.mkdir(parents=True, exist_ok=True)

    out_path = PROJECT_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve model from settings if not overridden on CLI
    s = get_settings()
    if args.model:
        parts = args.model.split("/", 1)
        provider = parts[0] if len(parts) == 2 else s["llm1_provider"]
        model_id = parts[1] if len(parts) == 2 else parts[0]
    else:
        provider = s["llm1_provider"]
        model_id = s["llm1_model"]

    client = ModelClient(provider=provider, model=model_id)
    print(f"[config] mapping model: {provider}/{model_id}\n")

    # Import FormalStrategy here (needs sys.path set above)
    from strategies.formal import FormalStrategy
    fs = FormalStrategy(runs_dir=str(artifacts_base))

    # ── Load dataset ───────────────────────────────────────────────────────────
    rows = load_dataset(str(dataset_path))
    if args.offset:
        rows = rows[args.offset:]
    if args.limit:
        rows = rows[:args.limit]
    print(f"Loaded {len(rows)} rows from {dataset_path.name}\n")

    results = []
    correct = total_labeled = 0

    for idx, row in enumerate(rows, 1):
        row_id   = row.row_id or str(idx)
        gold     = _norm_gold(row.ground_truth or row.raw.get("generate_HIPAA_type", ""))
        chars_raw = row.raw.get("generate_characteristics", "")
        question  = row.question

        print(f"[{idx}/{len(rows)}]  row={row_id}  gold={gold}")
        print(f"  Q: {question[:80]}…")

        # Skip if artifact dir already exists and has output
        row_dir = artifacts_base / f"row_{row_id}"
        if args.skip_existing and (row_dir / "output").exists():
            # Try to read existing result
            result_json = row_dir / "result.json"
            if result_json.exists():
                saved = json.loads(result_json.read_text())
                verdict = _norm_verdict(saved.get("verdict", ""))
                match = "Y" if gold and verdict == gold else ("N" if gold else "")
                print(f"  [skip] verdict={verdict}  match={match}")
                results.append({
                    "row_id": row_id, "gold_label": gold, "verdict": verdict,
                    "match": match, "citations": saved.get("citations", ""),
                    "scenario_json": saved.get("scenario_json", ""),
                    "generated_facts": saved.get("generated_facts", ""),
                    "explanation_tree": saved.get("explanation_tree", ""),
                    "artifact_dir": str(row_dir), "latency_s": saved.get("latency_seconds", ""),
                    "error": saved.get("error", ""),
                })
                if match == "Y": correct += 1
                if match in ("Y", "N"): total_labeled += 1
                print()
                continue

        if not chars_raw.strip():
            print("  [skip] no generate_characteristics")
            results.append({"row_id": row_id, "gold_label": gold, "verdict": "ERROR",
                            "match": "", "error": "no generate_characteristics"})
            print(); continue

        t0 = time.time()

        # Step 1: Map characteristics → DatalogScenario
        fields = _map_characteristics(chars_raw, client)
        if fields is None:
            elapsed = round(time.time() - t0, 2)
            print(f"  [error] characteristics mapping failed  ({elapsed}s)")
            results.append({"row_id": row_id, "gold_label": gold, "verdict": "ERROR",
                            "match": "", "error": "characteristics mapping failed",
                            "latency_s": elapsed})
            print(); continue

        scenario = _build_scenario(fields, idx, question, chars_raw)
        scenario_json = json.dumps(fields)
        print(f"  scenario: sender={scenario.sender_role}  receiver={scenario.receiver_role}"
              f"  attr={scenario.attribute}  purpose={scenario.purpose}")

        # Step 2: Run Soufflé (engine isolation — no LLM2)
        row_dir.mkdir(parents=True, exist_ok=True)
        try:
            engine_result = fs._run_souffle(scenario, str(row_dir))
        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            print(f"  [error] Soufflé failed: {e}  ({elapsed}s)")
            results.append({"row_id": row_id, "gold_label": gold, "verdict": "ERROR",
                            "match": "", "error": str(e), "latency_s": elapsed,
                            "scenario_json": scenario_json})
            print(); continue

        elapsed   = round(time.time() - t0, 2)
        verdict   = _norm_verdict(engine_result.verdict)
        match     = "Y" if gold and verdict == gold else ("N" if gold else "")
        citations = ", ".join(engine_result.citations)

        # Save result.json for skip-existing logic
        saved_data = {
            "verdict": verdict, "citations": engine_result.citations,
            "scenario_json": scenario_json,
            "generated_facts": engine_result.generated_facts,
            "explanation_tree": engine_result.explanation_tree,
            "error": engine_result.error_message,
            "latency_seconds": elapsed,
        }
        (row_dir / "result.json").write_text(json.dumps(saved_data, indent=2))

        sym = "✓" if match == "Y" else ("✗" if match == "N" else "?")
        print(f"  {sym} verdict={verdict}  gold={gold}  citations={citations}  ({elapsed}s)")
        if engine_result.error_message:
            print(f"  [souffle err] {engine_result.error_message}")

        results.append({
            "row_id": row_id, "gold_label": gold, "verdict": verdict, "match": match,
            "citations": citations,
            "scenario_json": scenario_json,
            "generated_facts": engine_result.generated_facts[:500] if engine_result.generated_facts else "",
            "explanation_tree": engine_result.explanation_tree[:500] if engine_result.explanation_tree else "",
            "artifact_dir": str(row_dir),
            "latency_s": elapsed,
            "error": engine_result.error_message,
        })

        if match == "Y": correct += 1
        if match in ("Y", "N"): total_labeled += 1
        print()
        if args.delay:
            time.sleep(args.delay)

    # ── Summary ────────────────────────────────────────────────────────────────
    print("=" * 60)
    print("COMPONENT 1 — SOUFFLÉ ENGINE ISOLATION")
    print("=" * 60)
    print(f"  Rows processed:   {len(results)}")
    print(f"  Labeled:          {total_labeled}")
    if total_labeled:
        print(f"  Accuracy:         {correct/total_labeled:.1%}  ({correct}/{total_labeled})")
    errors = sum(1 for r in results if r.get("verdict") == "ERROR")
    print(f"  Errors:           {errors}")
    print(f"  Artifacts dir:    {artifacts_base}")

    # ── Write CSV ──────────────────────────────────────────────────────────────
    if results:
        fieldnames = ["row_id", "gold_label", "verdict", "match", "citations",
                      "scenario_json", "generated_facts", "explanation_tree",
                      "artifact_dir", "latency_s", "error"]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(results)
        print(f"\n  Summary CSV:      {out_path}")
    print()


if __name__ == "__main__":
    main()
