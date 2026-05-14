#!/usr/bin/env python3
"""
evaluate_llm1.py — LLM1 field-level extraction accuracy

Two modes:

  --gold <csv>       Small hand-annotated gold standard (any size).
                     Columns: question, sender_role, receiver_role, attribute,
                     purpose, same_org, is_business_associate, etc.

  --goldcoin <csv>   Full 107-row GoldCoin benchmark.
                     Uses generate_characteristics as ground truth via a
                     built-in keyword mapping table (no extra API calls).

Usage:
    python evaluate_llm1.py --gold data/llm1_gold_standard.csv
    python evaluate_llm1.py --goldcoin data/goldcoin.csv \\
                            --model anthropic/claude-sonnet-4-6
    python evaluate_llm1.py --gold data/llm1_gold_standard.csv \\
                            --model ollama/llama3.3:70b-instruct-q4_0
"""

import argparse, ast, csv, sys, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "app"))
sys.path.insert(0, str(PROJECT_ROOT / "connector"))

# ── Field definitions ────────────────────────────────────────────────────────

STRING_FIELDS = ["sender_role", "receiver_role", "attribute", "purpose"]
BOOL_FIELDS   = [
    "same_org", "is_business_associate",
    "is_guardian_of_subject", "obtained_authorization_164_508",
]
ALL_FIELDS = STRING_FIELDS + BOOL_FIELDS


def _parse_bool(val) -> bool:
    if isinstance(val, bool): return val
    return str(val).strip().lower() in ("true", "1", "yes")


# Cross-vocabulary normalization: maps gold-standard / natural-language strings
# to the canonical Soufflé hierarchy constants so that comparisons are
# vocabulary-agnostic (e.g. "government-agency" == "government-entity").
_ALIAS_TO_SOUFFLE: dict[str, str] = {
    # roles
    "government-agency":         "government-entity",
    "government agency":         "government-entity",
    "the government":            "government-entity",
    "employer":                  "individual",
    "attorney":                  "individual",
    "lawyer":                    "individual",
    "social worker":             "individual",
    "patient":                   "individual",
    "consumer":                  "individual",
    "law-enforcement":           "law-enforcement-official",
    "law enforcement":           "law-enforcement-official",
    "police":                    "law-enforcement-official",
    "healthcare-clearinghouse":  "clearinghouse",
    "healthcare clearinghouse":  "clearinghouse",
    "health care provider":      "covered-entity",
    "healthcare provider":       "covered-entity",
    "medical provider":          "covered-entity",
    "provider":                  "covered-entity",
    # Soufflé subtypes of covered-entity — predicting a specific subtype is
    # correct when the gold says "covered-entity" (hospital IS a covered entity).
    "hospital":                  "covered-entity",
    "doctor":                    "covered-entity",
    "pharmacist":                "covered-entity",
    "nurse":                     "covered-entity",
    "psychiatrist":              "covered-entity",
    "lab-technician":            "covered-entity",
    "health-insurance-issuer":   "covered-entity",
    "hmo":                       "covered-entity",
    "group-health-plan":         "covered-entity",
    "health-plan":               "covered-entity",
    "clearinghouse":             "covered-entity",
    # government subtypes
    "government-authority":      "government-entity",
    "public-health-authority":   "government-entity",
    "oversight-agency":          "government-entity",
    "guardian":                  "legal-guardian",
    "family-member":             "individual",
    "third-party":               "individual",
    "media":                     "individual",
    "secretary":                 "authorized-federal-official",
    # attributes
    "mental-health":             "psychotherapy-notes",
    "mental health":             "psychotherapy-notes",
    "substance-abuse":           "substance-abuse-records",
    "genetic-information":       "genetic-info",
    "genetic information":       "genetic-info",
    "immunization-records":      "medical-record",
    "immunization records":      "medical-record",
    "radiology-results":         "lab-results",
    "radiology results":         "lab-results",
    "billing-records":           "billing-record",
    "billing records":           "billing-record",
    "insurance-information":     "billing-record",
    "insurance information":     "phi",
    "demographic-data":          "demographic-info",
    "appointment-records":       "medical-record",
    # purposes
    "public-health":             "public-health",
    "oversight":                 "health-oversight",
    "employment":                "healthcare-operations",
    "marketing":                 "marketing",
    "emergency":                 "emergency-treatment",
    "patient-access":            "treatment",
}


def _normalize_field(val: str) -> str:
    """Normalize a field value to its canonical Soufflé constant."""
    v = val.strip().lower()
    # direct alias lookup
    if v in _ALIAS_TO_SOUFFLE:
        return _ALIAS_TO_SOUFFLE[v]
    # also try without hyphens (handles "medical_record" etc.)
    v2 = v.replace("_", "-")
    if v2 in _ALIAS_TO_SOUFFLE:
        return _ALIAS_TO_SOUFFLE[v2]
    # try the llm1_extractor maps
    try:
        from connector.llm1_extractor import LLM1Extractor
        e = object.__new__(LLM1Extractor)
        e._prompt_path = "(eval-normalize)"
        d = e._postprocess({
            "purpose": v2 if "purpose" in ["purpose"] else "treatment",
            "sender_role": v2, "receiver_role": v2, "attribute": v2,
            "extra_facts": [],
        }, "")
        # just return the cleaned field
    except Exception:
        pass
    return v2


def _compare(gold_val, pred_val, field: str) -> bool:
    if field in BOOL_FIELDS:
        return _parse_bool(gold_val) == bool(pred_val)
    g = _normalize_field(str(gold_val))
    p = _normalize_field(str(pred_val))
    return g == p


# ── GoldCoin characteristics → Soufflé constants mapping ─────────────────────
# Keyword-based lookup: longest match wins (avoids extra API calls).

_ROLE_MAP = [
    # (substring to match in natural-language role, soufflé constant)
    ("secretary of health",  "secretary"),
    ("public health auth",   "public-health-authority"),
    ("public health",        "public-health-authority"),
    ("law enforcement",      "law-enforcement"),
    ("judicial",             "law-enforcement"),
    ("court",                "law-enforcement"),
    ("police",               "law-enforcement"),
    ("business associate",   "business-associate"),
    ("health plan",          "health-plan"),
    ("insur",                "health-plan"),
    ("health care provider", "covered-entity"),
    ("healthcare provider",  "covered-entity"),
    ("medical provider",     "covered-entity"),
    ("hospital",             "covered-entity"),
    ("clinic",               "covered-entity"),
    ("covered entity",       "covered-entity"),
    ("covered-entity",       "covered-entity"),
    ("clearinghouse",        "healthcare-clearinghouse"),
    ("researcher",           "researcher"),
    ("research",             "researcher"),
    ("employer",             "employer"),
    ("coroner",              "coroner"),
    ("medical examiner",     "coroner"),
    ("patient",              "patient"),
    ("individual",           "individual"),
    ("attorney",             "attorney"),
    ("lawyer",               "attorney"),
    ("family",               "family-member"),
    ("parent",               "guardian"),
    ("guardian",             "guardian"),
    ("government",           "government-agency"),
    ("secretary",            "secretary"),
    ("media",                "media"),
    ("third",                "third-party"),
]

_ATTR_MAP = [
    ("psychotherapy",        "psychotherapy-notes"),
    ("therapy note",         "psychotherapy-notes"),
    ("mental health",        "mental-health"),
    ("psychiatric",          "mental-health"),
    ("substance abuse",      "substance-abuse"),
    ("drug",                 "substance-abuse"),
    ("hiv",                  "hiv-status"),
    ("genetic",              "genetic-information"),
    ("immunization",         "immunization-records"),
    ("vaccination",          "immunization-records"),
    ("radiology",            "radiology-results"),
    ("imaging",              "radiology-results"),
    ("lab result",           "lab-results"),
    ("laboratory",           "lab-results"),
    ("test result",          "lab-results"),
    ("prescription",         "prescription"),
    ("medication",           "prescription"),
    ("billing",              "billing-records"),
    ("payment record",       "billing-records"),
    ("insurance",            "insurance-information"),
    ("health plan",          "insurance-information"),
    ("demographic",          "demographic-data"),
    ("appointment",          "appointment-records"),
    ("diagnosis",            "diagnosis"),
    ("medical record",       "medical-record"),
    ("health record",        "medical-record"),
    ("clinical record",      "medical-record"),
    ("patient record",       "medical-record"),
    ("record",               "medical-record"),
]

_PURPOSE_MAP = [
    ("treatment",            "treatment"),
    ("health care operation","healthcare-operations"),
    ("healthcare operation", "healthcare-operations"),
    ("operation",            "healthcare-operations"),
    ("payment",              "payment"),
    ("billing",              "payment"),
    ("research",             "research"),
    ("public health",        "public-health"),
    ("disease control",      "public-health"),
    ("law enforcement",      "law-enforcement"),
    ("criminal",             "law-enforcement"),
    ("investigation",        "law-enforcement"),
    ("subpoena",             "law-enforcement"),
    ("court order",          "law-enforcement"),
    ("litigation",           "law-enforcement"),
    ("patient access",       "patient-access"),
    ("access request",       "patient-access"),
    ("marketing",            "marketing"),
    ("employment",           "employment"),
    ("oversight",            "oversight"),
    ("audit",                "oversight"),
    ("emergency",            "emergency"),
    ("training",             "training-programs"),
    ("national security",    "national-security"),
]


def _keyword_map(text: str, mapping: list) -> str:
    """Return the first matching Soufflé constant by substring search."""
    t = text.lower()
    for substr, constant in mapping:
        if substr in t:
            return constant
    return ""


def _goldcoin_to_gold_fields(raw_chars: str) -> dict:
    """Parse generate_characteristics and map to DatalogScenario field values."""
    gold = {f: "" for f in ALL_FIELDS}
    if not raw_chars.strip():
        return gold
    try:
        chars = ast.literal_eval(raw_chars.strip())
    except Exception:
        return gold
    if not isinstance(chars, dict):
        return gold

    s_role  = chars.get("Sender Role", chars.get("sender_role", ""))
    r_role  = chars.get("Recipient Role", chars.get("receiver_role", ""))
    attr    = chars.get("Type", chars.get("attribute", ""))
    purpose = chars.get("Purpose", chars.get("purpose", ""))
    consent = chars.get("Consented By", "")

    gold["sender_role"]   = _keyword_map(s_role,  _ROLE_MAP)    or "covered-entity"
    gold["receiver_role"] = _keyword_map(r_role,  _ROLE_MAP)    or "individual"
    gold["attribute"]     = _keyword_map(attr,    _ATTR_MAP)    or "medical-record"
    gold["purpose"]       = _keyword_map(purpose, _PURPOSE_MAP) or "treatment"

    # Boolean heuristics
    gold["is_business_associate"] = str(
        "business associate" in s_role.lower() or "business associate" in r_role.lower()
    ).lower()

    consent_lower = consent.lower()
    gold["obtained_authorization_164_508"] = str(
        "patient" in consent_lower or "individual" in consent_lower
        or "consent" in consent_lower or "authorization" in consent_lower
    ).lower()

    gold["same_org"]                = "false"
    gold["is_guardian_of_subject"]  = str(
        "guardian" in s_role.lower() or "parent" in s_role.lower()
    ).lower()

    return gold


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Evaluate LLM1 field-level extraction accuracy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--gold", help="Hand-annotated gold standard CSV")
    group.add_argument("--goldcoin", help="GoldCoin CSV (uses generate_characteristics)")
    parser.add_argument("--model", default=None,
                        help="Override LLM1 model: provider/model")
    parser.add_argument("--out", default="evaluate_llm1_results.csv",
                        help="Output CSV (default: evaluate_llm1_results.csv)")
    parser.add_argument("--regulation", default="hipaa")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0,
                        help="Skip first N rows before applying --limit")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="Seconds to sleep between rows (prevents Ollama timeouts on large models)")
    args = parser.parse_args()

    # ── Apply model override (in-memory — no file write needed) ──────────────
    if args.model:
        from connector.settings import get_settings
        parts = args.model.split("/", 1)
        s = get_settings()
        if len(parts) == 2:
            s["llm1_provider"] = parts[0]
            s["llm1_model"]    = parts[1]
        else:
            s["llm1_model"] = parts[0]
        print(f"[config] LLM1 model set to: {args.model}")

    if args.regulation != "hipaa":
        from connector.settings import get_settings
        get_settings()["active_regulation"] = args.regulation

    from connector.llm1_extractor import LLM1Extractor
    from connector.settings import get_settings

    s = get_settings()
    print(f"[config] LLM1 provider={s.get('llm1_provider','?')}  model={s.get('llm1_model','?')}\n")
    extractor = LLM1Extractor()

    # ── Load rows ──────────────────────────────────────────────────────────────
    if args.gold:
        gold_path = Path(args.gold)
        if not gold_path.exists():
            print(f"ERROR: {gold_path} not found", file=sys.stderr); sys.exit(1)
        with open(gold_path, newline="", encoding="utf-8") as f:
            raw_rows = list(csv.DictReader(f))
        if args.offset:
            raw_rows = raw_rows[args.offset:]
        if args.limit:
            raw_rows = raw_rows[:args.limit]
        # Normalise: gold rows are already in the right format
        eval_rows = [
            {"question": r["question"], "gold_fields": {f: r.get(f, "") for f in ALL_FIELDS}}
            for r in raw_rows
        ]
        print(f"Mode: --gold  ({len(eval_rows)} rows from {gold_path.name})\n")

    else:  # --goldcoin
        from connector.dataset_loader import load_dataset
        gc_path = Path(args.goldcoin)
        if not gc_path.exists():
            print(f"ERROR: {gc_path} not found", file=sys.stderr); sys.exit(1)
        gc_rows = load_dataset(str(gc_path))
        if args.offset:
            gc_rows = gc_rows[args.offset:]
        if args.limit:
            gc_rows = gc_rows[:args.limit]
        eval_rows = [
            {
                "question": r.question,
                "gold_fields": _goldcoin_to_gold_fields(r.raw.get("generate_characteristics", "")),
            }
            for r in gc_rows
        ]
        print(f"Mode: --goldcoin  ({len(eval_rows)} rows from {gc_path.name})\n")
        print("  Gold standard: generate_characteristics → keyword mapping\n")

    # ── Evaluation loop ───────────────────────────────────────────────────────
    results       = []
    field_correct = {f: 0 for f in ALL_FIELDS}
    field_total   = {f: 0 for f in ALL_FIELDS}

    for idx, item in enumerate(eval_rows, 1):
        question    = item["question"].strip()
        gold_fields = item["gold_fields"]
        print(f"[{idx}/{len(eval_rows)}] {question[:80]}…")
        t0 = time.time()

        try:
            scenario, raw_json = extractor.extract(question)
            elapsed = round(time.time() - t0, 2)
            error   = ""
        except Exception as e:
            elapsed  = round(time.time() - t0, 2)
            error    = str(e)
            scenario = None
            raw_json = ""
            print(f"  ERROR: {e}")

        rec = {"question": question, "error": error, "latency_s": elapsed, "raw_json": raw_json}

        for field in ALL_FIELDS:
            gold_val = str(gold_fields.get(field, "")).strip()
            if not gold_val:
                rec[f"gold_{field}"] = ""
                rec[f"pred_{field}"] = str(getattr(scenario, field, "")) if scenario else ""
                rec[f"match_{field}"] = ""
                continue

            pred_val = getattr(scenario, field, None) if scenario else None
            match    = _compare(gold_val, pred_val, field) if scenario else False

            rec[f"gold_{field}"]  = gold_val
            rec[f"pred_{field}"]  = str(pred_val) if pred_val is not None else ""
            rec[f"match_{field}"] = "1" if match else "0"

            field_correct[field] += int(match)
            field_total[field]   += 1

            print(f"  {'✓' if match else '✗'} {field}: gold={gold_val!r}  pred={pred_val!r}")

        print(f"  latency: {elapsed}s\n")
        results.append(rec)
        if args.delay:
            time.sleep(args.delay)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=" * 60)
    print(f"LLM1 FIELD-LEVEL ACCURACY  "
          f"({'goldcoin / generate_characteristics' if args.goldcoin else args.gold})")
    print("=" * 60)
    all_correct = all_total = 0
    for field in ALL_FIELDS:
        if field_total[field] == 0:
            print(f"  {field:45s}  N/A")
            continue
        acc = field_correct[field] / field_total[field]
        all_correct += field_correct[field]
        all_total   += field_total[field]
        print(f"  {field:45s}  {acc:6.1%}  ({field_correct[field]}/{field_total[field]})")
    if all_total:
        print(f"\n  {'OVERALL':45s}  {all_correct/all_total:6.1%}  ({all_correct}/{all_total})")

    if results:
        out_path = Path(args.out)
        fieldnames = list(results[0].keys())
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\nDetailed results written to: {out_path}")


if __name__ == "__main__":
    main()
