#!/usr/bin/env python3
"""
eval_e2e.py — Component 3: Full end-to-end pipeline

Runs the complete formal pipeline on all 107 GoldCoin rows:
  LLM1 → Soufflé engine → LLM2

Models default to whatever is configured in settings (UI Settings tab or
.compliancegpt_settings.json). Override per-stage with --llm1 and --llm2
to run model-swap ablations (e.g. llama3 for extraction, phi4 for explanation).

Compares the final verdict against GoldCoin gold labels (generate_HIPAA_type).
The accuracy gap vs eval_component1_souffle.py quantifies LLM1's error contribution.

Output: data/eval_e2e.csv

Usage:
    python eval_e2e.py
    python eval_e2e.py --llm1 ollama/llama3.2:latest --llm2 ollama/llama3.2:latest
    python eval_e2e.py --llm1 anthropic/claude-sonnet-4-6 --llm2 ollama/phi4:latest
    python eval_e2e.py --skip-existing --limit 10
"""

import argparse, csv, os, sys, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from connector.dataset_loader import load_dataset
from connector.settings import get_settings


def _norm_verdict(v: str) -> str:
    v = v.strip().upper()
    return "PERMITTED" if v in ("ALLOWED", "PERMITTED") else v


def _norm_gold(v: str) -> str:
    v = v.strip().lower()
    if v in ("permit", "permitted", "allowed", "yes"): return "PERMITTED"
    if v in ("forbid", "forbidden", "denied", "no"):   return "DENIED"
    return v.upper()


def _apply_models(llm1_str: str | None, llm2_str: str | None):
    """Override LLM1 and/or LLM2 provider/model in the settings singleton (in-memory).
    If either arg is None, the current settings value is kept unchanged.
    """
    s = get_settings()

    def _parse(model_str, default_provider):
        if "/" in model_str:
            return model_str.split("/", 1)
        return default_provider, model_str

    if llm1_str:
        p, m = _parse(llm1_str, s["llm1_provider"])
        s["llm1_provider"], s["llm1_model"] = p, m

    if llm2_str:
        p, m = _parse(llm2_str, s["llm2_provider"])
        s["llm2_provider"], s["llm2_model"] = p, m

    print(f"[config] LLM1 → {s['llm1_provider']}/{s['llm1_model']}")
    print(f"[config] LLM2 → {s['llm2_provider']}/{s['llm2_model']}")


def main():
    parser = argparse.ArgumentParser(
        description="Component 3: Full end-to-end pipeline accuracy (Claude)"
    )
    parser.add_argument("--dataset", default="data/goldcoin.csv",
                        help="GoldCoin CSV path (default: data/goldcoin.csv)")
    parser.add_argument("--llm1", default=None,
                        help="LLM1 extraction model: provider/model "
                             "(default: reads llm1_provider/llm1_model from settings)")
    parser.add_argument("--llm2", default=None,
                        help="LLM2 explanation model: provider/model "
                             "(default: reads llm2_provider/llm2_model from settings)")
    parser.add_argument("--out", default="data/eval_e2e.csv",
                        help="Output CSV (default: data/eval_e2e.csv)")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to process")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip rows already in the output CSV")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="Seconds to sleep between rows (prevents Ollama timeouts on large models)")
    args = parser.parse_args()

    dataset_path = PROJECT_ROOT / args.dataset
    if not dataset_path.exists():
        print(f"ERROR: Dataset not found: {dataset_path}", file=sys.stderr); sys.exit(1)

    out_path = PROJECT_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Apply model overrides before importing FormalStrategy (reads settings on init)
    _apply_models(args.llm1, args.llm2)

    # Now import strategy (settings already set)
    from strategies.formal import FormalStrategy

    # Load existing rows for skip-existing
    existing_ids: set = set()
    existing_rows: list = []
    if args.skip_existing and out_path.exists():
        with open(out_path, newline="", encoding="utf-8") as f:
            existing_rows = list(csv.DictReader(f))
            for r in existing_rows:
                existing_ids.add(r.get("row_id", ""))

    rows = load_dataset(str(dataset_path))
    if args.limit:
        rows = rows[:args.limit]
    print(f"\nLoaded {len(rows)} rows from {dataset_path.name}\n")

    fs = FormalStrategy()
    results = list(existing_rows)

    correct = total_labeled = errors = 0
    # Count stats from pre-existing results
    for r in existing_rows:
        if r.get("match") == "Y": correct += 1
        if r.get("match") in ("Y", "N"): total_labeled += 1
        if r.get("verdict") == "ERROR": errors += 1

    for idx, row in enumerate(rows, 1):
        row_id = row.row_id or str(idx)
        gold   = _norm_gold(row.ground_truth or row.raw.get("generate_HIPAA_type", ""))

        if args.skip_existing and row_id in existing_ids:
            print(f"[{idx}/{len(rows)}] row={row_id}  skip")
            continue

        question = row.question
        print(f"[{idx}/{len(rows)}]  row={row_id}  gold={gold}")
        print(f"  Q: {question[:80]}…")

        t0 = time.time()
        try:
            result = fs.run(question)
            elapsed = round(time.time() - t0, 2)
        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            print(f"  [error] {e}  ({elapsed}s)\n")
            results.append({
                "row_id": row_id, "gold_label": gold, "verdict": "ERROR",
                "match": "", "answer": "", "citations": "",
                "scenario_json": "", "latency_s": elapsed, "error": str(e),
            })
            errors += 1
            print(); continue

        verdict = _norm_verdict(result.verdict)
        match   = "Y" if gold and verdict == gold else ("N" if gold else "")
        citations = ", ".join(result.citations)

        sym = "✓" if match == "Y" else ("✗" if match == "N" else "?")
        print(f"  {sym} verdict={verdict}  gold={gold}  cit={citations}  ({elapsed}s)")

        results.append({
            "row_id":       row_id,
            "gold_label":   gold,
            "verdict":      verdict,
            "match":        match,
            "answer":       result.answer[:500] if result.answer else "",
            "citations":    citations,
            "scenario_json": result.scenario_json[:300] if result.scenario_json else "",
            "latency_s":    elapsed,
            "error":        result.error or "",
        })

        if match == "Y": correct += 1
        if match in ("Y", "N"): total_labeled += 1
        print()
        if args.delay:
            time.sleep(args.delay)

    # ── Summary ────────────────────────────────────────────────────────────────
    s = get_settings()
    print("=" * 60)
    print("COMPONENT 3 — FULL END-TO-END PIPELINE")
    print("=" * 60)
    print(f"  LLM1:             {s['llm1_provider']}/{s['llm1_model']}")
    print(f"  LLM2:             {s['llm2_provider']}/{s['llm2_model']}")
    print(f"  Rows processed:   {len(results)}")
    print(f"  Labeled:          {total_labeled}")
    if total_labeled:
        print(f"  Accuracy:         {correct/total_labeled:.1%}  ({correct}/{total_labeled})")
    print(f"  Errors:           {errors}")

    if results:
        fieldnames = ["row_id", "gold_label", "verdict", "match", "answer",
                      "citations", "scenario_json", "latency_s", "error"]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(results)
        print(f"\n  Output CSV:       {out_path}")
    print()


if __name__ == "__main__":
    main()
