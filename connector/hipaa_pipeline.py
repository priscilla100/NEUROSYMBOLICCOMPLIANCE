"""
hipaa_pipeline.py
─────────────────────────────────────────────────────────────────────────────
End-to-end HIPAA compliance pipeline.

    User question
        → LLM1Extractor  → DatalogScenario
        → HIPAAEngine    → EngineResult
        → LLM2Explainer  → human-readable answer

QUICKSTART:

    python hipaa_pipeline.py \
        --souffle-dir /path/to/ComplianceGPT/datalog_engine \
        --question "Can I see my lab results before my doctor reviews them?"

    # or interactive mode:
    python hipaa_pipeline.py --souffle-dir /path/to/datalog_engine

BATCH MODE (against your benchmark CSV):

    python hipaa_pipeline.py \
        --souffle-dir /path/to/datalog_engine \
        --benchmark /path/to/your_benchmark.csv \
        --output results.csv
"""

import os
import sys
import csv
import json
import argparse
from datetime import datetime

from hipaa_engine import HIPAAEngine, DatalogScenario
from llm1_extractor import LLM1Extractor
from llm2_explainer import LLM2Explainer
# ─────────────────────────────────────────────────────────────────────────────
# Single question
# ─────────────────────────────────────────────────────────────────────────────

def run_single(
    question: str,
    engine: HIPAAEngine,
    extractor: LLM1Extractor,
    explainer: LLM2Explainer,
    verbose: bool = False,
) -> dict:
    """
    Run the full pipeline for a single question.
    Returns a dict with all intermediate and final outputs.
    """
    print(f"\n{'='*60}")
    print(f"QUESTION: {question}")
    print(f"{'='*60}")

    # Step 1: Extract scenario
    print("\n[1/3] Extracting scenario with LLM1...")
    scenario, raw_json = extractor.extract(question)
    if verbose:
        print("  Extracted JSON:")
        print("  " + raw_json.replace("\n", "\n  "))

    # Step 2: Run formal engine
    print("[2/3] Running Souffle compliance engine...")
    result = engine.check(scenario)
    print(f"  → VERDICT: {result.verdict}")
    if result.citations:
        print(f"  → CITATIONS: {', '.join(result.citations)}")
    if result.error_message:
        print(f"  → ERROR: {result.error_message}")

    # Step 3: Generate human-readable explanation
    print("[3/3] Generating explanation with LLM2...")
    answer = explainer.explain(question, result)
    print("\n" + answer)

    return {
        "question": question,
        "scenario_json": raw_json,
        "verdict": result.verdict,
        "citations": result.citations,
        "explanation_tree": result.explanation_tree,
        "answer": answer,
        "error": result.error_message,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Batch mode — runs against your benchmark CSV
# ─────────────────────────────────────────────────────────────────────────────

def run_benchmark(
    csv_path: str,
    engine: HIPAAEngine,
    extractor: LLM1Extractor,
    explainer: LLM2Explainer,
    output_path: str = "benchmark_results.csv",
    question_col: str = "question",
    answer_col: str = "answer",   # "Yes" / "No"
):
    """
    Run the pipeline against every row in a benchmark CSV.
    Compares engine verdict to ground truth and writes results.

    Your benchmark CSV columns:
        id, question, topic, complexity, answer, regulation, cross_references, explanation

    The 'answer' column should be "Yes" (disclosure allowed) or "No" (denied).
    """
    print(f"\nBATCH MODE: {csv_path}")
    print(f"Output: {output_path}\n")

    results = []
    correct = 0
    total = 0
    errors = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for i, row in enumerate(rows):
        question = row.get(question_col, "").strip()
        ground_truth_raw = row.get(answer_col, "").strip().lower()
        # Normalize ground truth: "yes" → expected ALLOWED, "no" → expected DENIED
        expected = "ALLOWED" if ground_truth_raw in ("yes", "permitted", "allowed", "true") else "DENIED"

        print(f"[{i+1}/{len(rows)}] {question[:70]}...")

        try:
            scenario, raw_json = extractor.extract(question)
            result = engine.check(scenario)
            answer = explainer.explain(question, result)

            match = (result.verdict == expected) or result.verdict == "ALLOWED" and expected == "ALLOWED"
            # More precise match
            match = result.verdict == expected

            if result.verdict not in ("ERROR", "UNKNOWN"):
                total += 1
                if match:
                    correct += 1

            results.append({
                "id": row.get("id", i+1),
                "question": question,
                "topic": row.get("topic", ""),
                "complexity": row.get("complexity", ""),
                "ground_truth": expected,
                "verdict": result.verdict,
                "match": "✓" if match else "✗",
                "citations": "; ".join(result.citations),
                "explanation_tree": result.explanation_tree[:200] if result.explanation_tree else "",
                "llm_answer": answer[:500],
                "error": result.error_message,
                "scenario_json": raw_json,
            })

            status = "✓ CORRECT" if match else f"✗ WRONG (expected {expected}, got {result.verdict})"
            print(f"  {status}")

        except Exception as e:
            errors += 1
            results.append({
                "id": row.get("id", i+1),
                "question": question,
                "topic": row.get("topic", ""),
                "complexity": row.get("complexity", ""),
                "ground_truth": expected,
                "verdict": "ERROR",
                "match": "✗",
                "citations": "",
                "explanation_tree": "",
                "llm_answer": "",
                "error": str(e),
                "scenario_json": "",
            })
            print(f"  ERROR: {e}")

    # Write results CSV
    if results:
        fieldnames = list(results[0].keys())
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

    # Print summary
    print(f"\n{'='*60}")
    print(f"BENCHMARK SUMMARY")
    print(f"{'='*60}")
    print(f"Total questions:  {len(rows)}")
    print(f"Evaluated:        {total}")
    print(f"Correct:          {correct}")
    print(f"Accuracy:         {correct/total*100:.1f}%" if total > 0 else "N/A")
    print(f"Errors/skipped:   {errors}")
    print(f"Results saved to: {output_path}")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="HIPAA Compliance Pipeline")
    parser.add_argument("--souffle-dir", required=True,
                        help="Path to your datalog_engine directory containing hipaa_*.dl files")
    parser.add_argument("--question", default=None,
                        help="Single HIPAA question to check")
    parser.add_argument("--benchmark", default=None,
                        help="Path to benchmark CSV file (batch mode)")
    parser.add_argument("--output", default="benchmark_results.csv",
                        help="Output CSV for benchmark results (default: benchmark_results.csv)")
    parser.add_argument("--souffle-binary", default="souffle",
                        help="Path to souffle binary (default: 'souffle' on PATH)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show extracted JSON scenario")
    args = parser.parse_args()

    # Initialize components
    # Resolve API key based on the active provider from settings (not Anthropic-only).
    # The ModelClient inside LLM1Extractor / LLM2Explainer will read the right key from
    # settings or env vars for whichever provider is configured.
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from connector.settings import get_settings
        _s = get_settings()
        _provider = _s["llm1_provider"]
        api_key = _s.get_api_key(_provider)
    except Exception:
        # Do not silently default to anthropic — use ollama as the safe local fallback
        _provider = os.environ.get("COMPLIANCE_PROVIDER", "anthropic")
        api_key = os.environ.get("ANTHROPIC_API_KEY", "") if _provider == "anthropic" else ""

    if not api_key:
        _key_env = {
            "anthropic":   "ANTHROPIC_API_KEY",
            "openai":      "OPENAI_API_KEY",
            "google":      "GOOGLE_API_KEY",
            "huggingface": "HUGGINGFACE_API_KEY",
        }.get(_provider, "ANTHROPIC_API_KEY")
        print(f"ERROR: No API key found for provider '{_provider}'. "
              f"Set {_key_env} or configure it in the Settings page.")
        sys.exit(1)

    engine    = HIPAAEngine(args.souffle_dir, souffle_binary=args.souffle_binary)
    extractor = LLM1Extractor()   # reads provider+model+key from settings
    explainer = LLM2Explainer()   # reads provider+model+key from settings

    if args.benchmark:
        run_benchmark(args.benchmark, engine, extractor, explainer, args.output)

    elif args.question:
        run_single(args.question, engine, extractor, explainer, verbose=args.verbose)

    else:
        # Interactive mode
        print("HIPAA Compliance Checker — Interactive Mode")
        print("Type your question and press Enter. Ctrl+C to exit.\n")
        while True:
            try:
                question = input("Your question: ").strip()
                if not question:
                    continue
                run_single(question, engine, extractor, explainer, verbose=args.verbose)
            except KeyboardInterrupt:
                print("\nGoodbye.")
                break
            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    main()
