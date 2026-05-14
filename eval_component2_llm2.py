#!/usr/bin/env python3
"""
eval_component2_llm2.py — Component 2: Soufflé output → LLM2 → user

Reads Component 1's summary CSV (data/eval_component1.csv), feeds each row's
Soufflé verdict + proof tree into LLM2 (Claude), and evaluates faithfulness:
  1. Verdict preservation
  2. Citation grounding
  3. Rubric scoring (if --rubric provided)

Creates the LLM2 explanation dataset for all 107 GoldCoin rows.

Usage:
    python eval_component2_llm2.py
    python eval_component2_llm2.py --component1 data/eval_component1.csv \\
        --model anthropic/claude-sonnet-4-6 --rubric data/explanation_rubric.csv
    python eval_component2_llm2.py --skip-existing --limit 10
"""

import argparse, ast, csv, os, re, sys, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from connector.hipaa_engine import EngineResult, DatalogScenario
from connector.llm2_explainer import LLM2Explainer
from connector.settings import get_settings

# Reuse faithfulness check helpers from evaluate_llm2.py
sys.path.insert(0, str(PROJECT_ROOT))
from evaluate_llm2 import (
    _check_verdict_preserved,
    _check_citation_grounded,
    _rubric_score,
    _load_rubric,
    _normalise_verdict,
)


def _reconstruct_engine_result(row: dict) -> EngineResult:
    """Rebuild a minimal EngineResult from a Component 1 CSV row."""
    citations_raw = row.get("citations", "")
    if citations_raw:
        cits = [c.strip() for c in citations_raw.split(",") if c.strip()]
    else:
        cits = []

    scenario = DatalogScenario(
        sender="sender", sender_role="covered-entity",
        receiver="receiver", receiver_role="individual",
        subject="patient", subject_category="adult",
        attribute="medical-record", purpose="treatment",
    )

    # Try to parse scenario_json back into scenario fields
    scenario_json = row.get("scenario_json", "")
    if scenario_json:
        try:
            import json as _json
            fields = _json.loads(scenario_json)
            scenario = DatalogScenario(
                sender      = "sender",
                sender_role = fields.get("sender_role", "covered-entity"),
                receiver    = "receiver",
                receiver_role = fields.get("receiver_role", "individual"),
                subject     = "patient",
                subject_category = fields.get("subject_category", "adult"),
                attribute   = fields.get("attribute", "medical-record"),
                purpose     = fields.get("purpose", "treatment"),
            )
        except Exception:
            pass

    return EngineResult(
        verdict          = row.get("verdict", "UNKNOWN"),
        scenario         = scenario,
        citations        = cits,
        explanation_tree = row.get("explanation_tree", ""),
        generated_facts  = row.get("generated_facts", ""),
        error_message    = row.get("error", ""),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Component 2: LLM2 explanation dataset from Soufflé outputs"
    )
    parser.add_argument("--component1", default="data/eval_component1.csv",
                        help="Component 1 summary CSV (default: data/eval_component1.csv)")
    parser.add_argument("--model", default=None,
                        help="LLM2 model: provider/model "
                             "(default: reads llm2_provider/llm2_model from settings)")
    parser.add_argument("--rubric", default="data/explanation_rubric.csv",
                        help="Rubric CSV for scoring (default: data/explanation_rubric.csv)")
    parser.add_argument("--dataset", default="data/goldcoin.csv",
                        help="GoldCoin CSV for original questions")
    parser.add_argument("--out", default="data/eval_component2.csv",
                        help="Output CSV (default: data/eval_component2.csv)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="Seconds to sleep between rows (prevents Ollama timeouts on large models)")
    args = parser.parse_args()

    c1_path = PROJECT_ROOT / args.component1
    if not c1_path.exists():
        print(f"ERROR: Component 1 CSV not found: {c1_path}\n"
              f"  Run eval_component1_souffle.py first.", file=sys.stderr)
        sys.exit(1)

    out_path = PROJECT_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load rubric
    rubric_rows = None
    rubric_path = PROJECT_ROOT / args.rubric
    if rubric_path.exists():
        rubric_rows = _load_rubric(rubric_path)
        print(f"[rubric] loaded {len(rubric_rows)} entries from {rubric_path.name}")

    # Load existing output for skip-existing
    existing_ids: set = set()
    if args.skip_existing and out_path.exists():
        with open(out_path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                existing_ids.add(r.get("row_id", ""))

    # Load original questions from goldcoin (to pass full narrative to LLM2)
    question_map: dict[str, str] = {}
    gc_path = PROJECT_ROOT / args.dataset
    if gc_path.exists():
        from connector.dataset_loader import load_dataset
        for gr in load_dataset(str(gc_path)):
            question_map[gr.row_id] = gr.question

    # Resolve LLM2 model from settings if not overridden on CLI
    s = get_settings()
    if args.model:
        model_str = args.model
    else:
        model_str = f"{s['llm2_provider']}/{s['llm2_model']}"
    explainer = LLM2Explainer(model=model_str)
    print(f"[config] LLM2 model: {model_str}\n")

    # Read Component 1 rows
    with open(c1_path, newline="", encoding="utf-8") as f:
        c1_rows = list(csv.DictReader(f))
    if args.limit:
        c1_rows = c1_rows[:args.limit]

    print(f"Processing {len(c1_rows)} rows from {c1_path.name}\n")

    results = []
    vp_total = cg_total = rubric_sum = rubric_n = 0
    processed = 0

    # If skip-existing, load previously written rows first
    if args.skip_existing and out_path.exists():
        with open(out_path, newline="", encoding="utf-8") as f:
            results = list(csv.DictReader(f))

    for idx, row in enumerate(c1_rows, 1):
        row_id  = row.get("row_id", str(idx))
        verdict = row.get("verdict", "")

        if verdict in ("ERROR", "UNKNOWN", ""):
            print(f"[{idx}/{len(c1_rows)}] row={row_id}  skip (verdict={verdict})")
            continue

        if args.skip_existing and row_id in existing_ids:
            print(f"[{idx}/{len(c1_rows)}] row={row_id}  skip (already done)")
            continue

        question = question_map.get(row_id, row.get("question", f"GoldCoin row {row_id}"))
        print(f"[{idx}/{len(c1_rows)}] row={row_id}  verdict={verdict}")
        print(f"  Q: {question[:80]}…")

        engine_result = _reconstruct_engine_result(row)
        t0 = time.time()

        try:
            explanation = explainer.explain(question, engine_result)
            elapsed = round(time.time() - t0, 2)
            error = ""
        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            explanation = f"(LLM2 error: {e})"
            error = str(e)
            print(f"  [error] {e}")

        # Faithfulness checks — build a pseudo-row for the helpers
        check_row = {
            "verdict": verdict,
            "answer": explanation,
            "citations": row.get("citations", ""),
            "question": question,
            "explanation_tree": row.get("explanation_tree", ""),
        }

        vp = _check_verdict_preserved(check_row)
        cg = _check_citation_grounded(check_row)
        vp_total += vp
        cg_total += cg

        rubric_score_val = ""
        if rubric_rows:
            rscores = _rubric_score(check_row, rubric_rows)
            if rscores:
                rubric_score_val = rscores["rubric_total"]
                rubric_sum += rscores["rubric_total"]
                rubric_n   += 1

        vs = "✓" if vp else "✗"
        cs = "✓" if cg else "✗"
        print(f"  {vs} verdict_preserved={vp}  {cs} citation_grounded={cg}"
              + (f"  rubric={rubric_score_val}/5" if rubric_score_val != "" else "")
              + f"  ({elapsed}s)")
        print()

        results.append({
            "row_id":              row_id,
            "gold_label":          row.get("gold_label", ""),
            "verdict":             verdict,
            "question":            question,
            "explanation":         explanation,
            "citations":           row.get("citations", ""),
            "verdict_preserved":   vp,
            "citation_grounded":   cg,
            "rubric_total":        rubric_score_val,
            "latency_s":           elapsed,
            "error":               error,
        })
        processed += 1
        if args.delay:
            time.sleep(args.delay)

    # ── Summary ────────────────────────────────────────────────────────────────
    n = processed
    print("=" * 60)
    print("COMPONENT 2 — LLM2 EXPLANATION FAITHFULNESS")
    print("=" * 60)
    print(f"  Rows explained:       {n}")
    if n:
        print(f"  Verdict preserved:    {vp_total/n:.1%}  ({vp_total}/{n})")
        print(f"  Citation grounded:    {cg_total/n:.1%}  ({cg_total}/{n})")
    if rubric_n:
        print(f"  Rubric avg score:     {rubric_sum/rubric_n:.2f}/5  (n={rubric_n})")

    if results:
        fieldnames = ["row_id", "gold_label", "verdict", "question", "explanation",
                      "citations", "verdict_preserved", "citation_grounded",
                      "rubric_total", "latency_s", "error"]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(results)
        print(f"\n  Output CSV:           {out_path}")
    print()


if __name__ == "__main__":
    main()
