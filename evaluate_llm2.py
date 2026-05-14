#!/usr/bin/env python3
"""
evaluate_llm2.py — LLM2 explanation faithfulness evaluation

Three automatic checks per formal-strategy result row:
  1. Verdict preservation  — explanation text contains the correct verdict word
  2. Citation grounding    — LLM2 citations are a subset of engine citations
  3. LLM-as-judge (opt.)   — capable model rates faithfulness 1–5

Optional rubric scoring (--rubric):
  Matches result rows to annotated rubric entries and scores on 5 dimensions:
  correct verdict stated / correct section cited / correct roles identified /
  correct PHI category mentioned / no contradiction with engine output.

Usage:
    python evaluate_llm2.py --results results/20260504_200149/
    python evaluate_llm2.py --results results/20260504_200149/ \
                            --judge anthropic/claude-sonnet-4-6
    python evaluate_llm2.py --results results/20260504_200149/ \
                            --rubric data/explanation_rubric.csv
    python evaluate_llm2.py --results results/20260504_200149/ \
                            --judge anthropic/claude-sonnet-4-6 \
                            --rubric data/explanation_rubric.csv \
                            --out my_llm2_eval.csv
"""

import argparse
import ast
import csv
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "app"))
sys.path.insert(0, str(PROJECT_ROOT / "connector"))


# ── Helpers ─────────────────────────────────────────────────────────────────

def _normalise_verdict(v: str) -> str:
    v = v.strip().upper()
    if v in ("ALLOWED", "PERMITTED"):
        return "PERMITTED"
    if v == "DENIED":
        return "DENIED"
    return v


def _check_verdict_preserved(row: dict) -> int:
    """1 if the explanation text contains the correct verdict word, else 0."""
    verdict = _normalise_verdict(row.get("verdict", ""))
    answer  = row.get("answer") or row.get("llm_answer") or "".upper()
    if verdict == "PERMITTED":
        return int("PERMITTED" in answer or "ALLOWED" in answer)
    if verdict == "DENIED":
        return int("DENIED" in answer or "NOT PERMITTED" in answer or "NOT ALLOWED" in answer)
    return 0


def _parse_citation_list(raw: str) -> set:
    """Parse a citations column that may be a Python list literal or CSV string."""
    if not raw or not raw.strip():
        return set()
    raw = raw.strip()
    if raw.startswith("["):
        try:
            items = ast.literal_eval(raw)
            return {str(c).strip() for c in items if c}
        except Exception:
            pass
    # Fallback: comma-separated
    return {c.strip() for c in raw.split(",") if c.strip()}


def _check_citation_grounded(row: dict) -> int:
    """1 if all citations mentioned in the explanation are from the engine's list."""
    engine_cits = _parse_citation_list(row.get("citations", ""))
    if not engine_cits:
        return 1  # engine gave no citations — nothing to check against

    # Extract §-style citation references from the explanation text
    answer = row.get("answer") or row.get("llm_answer") or ""
    # Match patterns like §164.506, 164.512(f), 45 CFR 164.524 etc.
    cited_in_answer = set(re.findall(r'1\d{2}\.\d{3}(?:\([a-z0-9]\))*', answer))

    if not cited_in_answer:
        return 1  # LLM2 didn't cite anything specific — conservatively pass

    # Each citation found in the explanation must appear in at least one engine citation
    for c in cited_in_answer:
        if not any(c in ec for ec in engine_cits):
            return 0
    return 1


_JUDGE_SYSTEM = """\
You are a legal accuracy evaluator for HIPAA compliance explanations.

You will be given:
1. A compliance question
2. The formal engine's proof tree (the ground-truth reasoning)
3. An LLM-generated explanation of the verdict

Rate the explanation's faithfulness to the proof tree on a scale of 1–5:
  5 = Fully faithful: all key facts, roles, and citations match the proof tree
  4 = Mostly faithful: minor wording differences, no factual errors
  3 = Partially faithful: correct verdict but some facts or citations wrong/missing
  2 = Weak: verdict mentioned but reasoning significantly diverges from proof tree
  1 = Unfaithful: contradicts the proof tree or contains invented facts

Respond with ONLY a JSON object: {"score": <1-5>, "reason": "<one sentence>"}
"""

def _judge_row(row: dict, model_client, judge_model: str) -> dict:
    """Call LLM-as-judge; returns {"score": int, "reason": str}."""
    question     = row.get("question", "")
    proof_tree   = row.get("explanation_tree", "") or row.get("generated_facts", "")
    answer       = row.get("answer") or row.get("llm_answer") or ""

    if not answer.strip():
        return {"score": 0, "reason": "no explanation to evaluate"}

    user_msg = (
        f"## Question\n{question}\n\n"
        f"## Proof Tree (ground truth)\n{proof_tree or '(not available)'}\n\n"
        f"## LLM Explanation\n{answer}"
    )

    try:
        raw = model_client.chat(
            system=_JUDGE_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
            model=judge_model,
            temperature=0.0,
            max_tokens=200,
        )
        import json as _json
        # Extract JSON block if wrapped in markdown
        m = re.search(r'\{.*?\}', raw, re.DOTALL)
        obj = _json.loads(m.group(0)) if m else _json.loads(raw)
        return {"score": int(obj.get("score", 0)), "reason": obj.get("reason", "")}
    except Exception as e:
        return {"score": 0, "reason": f"judge error: {e}"}


# ── Rubric scoring ───────────────────────────────────────────────────────────

def _load_rubric(path: Path) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _rubric_score(row: dict, rubric_rows: list) -> dict | None:
    """Match a result row to a rubric entry by question similarity; score 5 dims."""
    question = row.get("question", "").strip().lower()
    match = None
    for r in rubric_rows:
        if r["question"].strip().lower() == question:
            match = r
            break
    if match is None:
        return None

    answer  = row.get("answer") or row.get("llm_answer") or "".upper()
    verdict = _normalise_verdict(row.get("verdict", ""))

    # Dim 1: correct verdict stated
    d1 = int(
        (verdict == "PERMITTED" and ("PERMITTED" in answer or "ALLOWED" in answer)) or
        (verdict == "DENIED"    and ("DENIED" in answer or "NOT PERMITTED" in answer))
    )
    # Dim 2: correct section cited
    req_cits = [c.strip() for c in match.get("required_citations", "").split(",") if c.strip()]
    d2 = int(all(c.replace("§", "").replace(" ", "") in answer.replace(" ", "") for c in req_cits)) if req_cits else 1

    # Dim 3: correct party roles identified
    roles = [match.get("required_sender_role", ""), match.get("required_receiver_role", "")]
    d3 = int(all(r.strip().lower().replace("-", " ") in answer.lower().replace("-", " ")
                 for r in roles if r.strip()))

    # Dim 4: correct PHI category mentioned
    phi = match.get("required_phi_category", "").strip()
    d3_phi = int(phi.replace("-", " ").lower() in answer.lower().replace("-", " ")) if phi else 1

    # Dim 5: no contradiction — verdict in answer matches engine verdict
    engine_v = _normalise_verdict(row.get("verdict", ""))
    opposite = "DENIED" if engine_v == "PERMITTED" else "PERMITTED"
    d5 = int(opposite not in answer)

    total = d1 + d2 + d3 + d3_phi + d5
    return {
        "rubric_verdict_stated": d1,
        "rubric_citation_correct": d2,
        "rubric_roles_identified": d3,
        "rubric_phi_category": d3_phi,
        "rubric_no_contradiction": d5,
        "rubric_total": total,
        "rubric_max": 5,
    }


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Evaluate LLM2 explanation faithfulness")
    parser.add_argument("--results", required=True,
                        help="Results directory containing CSV files")
    parser.add_argument("--judge", default=None,
                        help="LLM-as-judge model: provider/model (e.g. anthropic/claude-sonnet-4-6)")
    parser.add_argument("--rubric", default=None,
                        help="Explanation rubric CSV path (optional)")
    parser.add_argument("--out", default="evaluate_llm2_results.csv",
                        help="Output CSV (default: evaluate_llm2_results.csv)")
    parser.add_argument("--strategy", default="formal",
                        help="Strategy to evaluate (default: formal)")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="Seconds to sleep between rows (prevents Ollama timeouts on large models)")
    args = parser.parse_args()

    results_dir = Path(args.results)
    if not results_dir.exists():
        print(f"ERROR: Results directory not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    # Find all CSVs that contain the target strategy
    csv_files = list(results_dir.rglob("*.csv"))
    print(f"Found {len(csv_files)} CSV file(s) in {results_dir}")

    # Load rubric if provided
    rubric_rows = None
    if args.rubric:
        rubric_path = Path(args.rubric)
        if not rubric_path.exists():
            print(f"WARNING: Rubric file not found: {rubric_path} — skipping rubric scoring")
        else:
            rubric_rows = _load_rubric(rubric_path)
            print(f"Loaded {len(rubric_rows)} rubric entries from {rubric_path}")

    # Load judge model client if requested
    model_client = None
    judge_model  = None
    if args.judge:
        from connector.model_client import ModelClient
        from connector.settings import get_settings, save_settings
        parts = args.judge.split("/", 1)
        s = get_settings()
        if len(parts) == 2:
            s["llm2_provider"] = parts[0]
            s["llm2_model"]    = parts[1]
        else:
            s["llm2_model"] = parts[0]
        save_settings(s)
        model_client = ModelClient()
        judge_model  = parts[1] if len(parts) == 2 else parts[0]
        print(f"[judge] Using: {args.judge}\n")

    # Process rows
    all_rows = []
    for csv_path in sorted(csv_files):
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                continue
            for row in reader:
                strat = row.get("strategy", "")
                if args.strategy not in strat and strat != args.strategy:
                    continue
                verdict = row.get("verdict", "")
                if verdict in ("ERROR", "UNKNOWN", ""):
                    continue
                all_rows.append(row)

    print(f"Evaluating {len(all_rows)} {args.strategy} rows with non-error verdicts\n")

    if not all_rows:
        print("No rows to evaluate. Check --results directory and --strategy filter.")
        sys.exit(0)

    out_rows = []
    totals = {"verdict_preserved": 0, "citation_grounded": 0, "judge_score_sum": 0,
              "judge_count": 0, "rubric_total_sum": 0, "rubric_count": 0}

    for idx, row in enumerate(all_rows, 1):
        q_short = row.get("question", "")[:70]
        print(f"[{idx}/{len(all_rows)}] {q_short}…")

        vp = _check_verdict_preserved(row)
        cg = _check_citation_grounded(row)
        totals["verdict_preserved"] += vp
        totals["citation_grounded"]  += cg

        rec = dict(row)
        rec["eval_verdict_preserved"]  = vp
        rec["eval_citation_grounded"]  = cg
        rec["eval_judge_score"]        = ""
        rec["eval_judge_reason"]       = ""

        verdict_sym = "✓" if vp else "✗"
        cit_sym     = "✓" if cg else "✗"
        print(f"  {verdict_sym} verdict_preserved={vp}  {cit_sym} citation_grounded={cg}")

        # LLM-as-judge
        if model_client and judge_model:
            jresult = _judge_row(row, model_client, judge_model)
            rec["eval_judge_score"]  = jresult["score"]
            rec["eval_judge_reason"] = jresult["reason"]
            totals["judge_score_sum"] += jresult["score"]
            totals["judge_count"]     += 1
            print(f"  judge={jresult['score']}/5  ({jresult['reason']})")

        # Rubric scoring
        if rubric_rows is not None:
            rscores = _rubric_score(row, rubric_rows)
            if rscores:
                rec.update(rscores)
                totals["rubric_total_sum"] += rscores["rubric_total"]
                totals["rubric_count"]     += 1
                print(f"  rubric={rscores['rubric_total']}/5")
            else:
                rec.update({k: "" for k in [
                    "rubric_verdict_stated", "rubric_citation_correct",
                    "rubric_roles_identified", "rubric_phi_category",
                    "rubric_no_contradiction", "rubric_total", "rubric_max",
                ]})

        out_rows.append(rec)
        print()
        if args.delay:
            time.sleep(args.delay)

    # ── Summary ──────────────────────────────────────────────────────────────
    n = len(all_rows)
    print("=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"  Rows evaluated:          {n}")
    print(f"  Verdict preserved:       {totals['verdict_preserved']/n:.1%}  ({totals['verdict_preserved']}/{n})")
    print(f"  Citation grounded:       {totals['citation_grounded']/n:.1%}  ({totals['citation_grounded']}/{n})")
    if totals["judge_count"]:
        avg_j = totals["judge_score_sum"] / totals["judge_count"]
        print(f"  LLM-as-judge avg score:  {avg_j:.2f}/5  (n={totals['judge_count']})")
    if totals["rubric_count"]:
        avg_r = totals["rubric_total_sum"] / totals["rubric_count"]
        print(f"  Rubric avg score:        {avg_r:.2f}/5  (n={totals['rubric_count']})")

    # ── Write output ──────────────────────────────────────────────────────────
    out_path = Path(args.out)
    if out_rows:
        fieldnames = list(out_rows[0].keys())
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(out_rows)
        print(f"\nDetailed results written to: {out_path}")


if __name__ == "__main__":
    main()
