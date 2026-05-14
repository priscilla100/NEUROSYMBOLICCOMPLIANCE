"""
app/cli.py
─────────────────────────────────────────────────────────────────────────────
ComplianceGPT CLI — four strategies, model override, batch eval.

USAGE:

  Interactive (formal strategy, default model):
    python app/cli.py

  Single question:
    python app/cli.py -q "Can I see my lab results?"

  Single question, specific strategy:
    python app/cli.py -q "Can I see my lab results?" --strategy baseline

  Single question, specific model:
    python app/cli.py -q "..." --strategy baseline --model openai/gpt-4o
    python app/cli.py -q "..." --strategy formal   --model anthropic/claude-haiku-4-5-20251001
    python app/cli.py -q "..." --strategy baseline --model ollama/llama3.2

  Compare all strategies on one question:
    python app/cli.py -q "..." --strategy all

  Batch eval:
    python app/cli.py --benchmark data/benchmark.csv --strategy formal --output results.csv
    python app/cli.py --benchmark data/benchmark.csv --strategy all --output results_all.csv

  Batch eval, override model:
    python app/cli.py --benchmark data/benchmark.csv --strategy baseline --model openai/gpt-4o

MODEL FORMAT:  provider/model-id
  anthropic/claude-sonnet-4-6
  openai/gpt-4o
  google/gemini-2.0-flash
  ollama/llama3.2
  huggingface/meta-llama/Llama-3.3-70B-Instruct
"""

import sys, os, csv, argparse, json, inspect
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from connector.settings import get_settings
from connector import config as _config

# ANSI
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
B = "\033[94m"; GRAY = "\033[90m"; BOLD = "\033[1m"; X = "\033[0m"


def _progress_printer(strategy: str, msg: str):
    """Print a step-level progress update from formal/agentic strategies."""
    tick = "✓" if "✓" in msg else "⠿"
    print(f"  {GRAY}[{strategy}] {msg}{X}")


# ─────────────────────────────────────────────────────────────────────────────
# Model override helper
# ─────────────────────────────────────────────────────────────────────────────

def apply_model_override(model_str: str):
    """
    Parse 'provider/model-id' and temporarily override settings.
    HuggingFace models: 'huggingface/org/model-name'
    """
    if not model_str or "/" not in model_str:
        return
    parts   = model_str.split("/", 1)
    provider = parts[0].lower()
    model_id = parts[1]
    s = get_settings()
    s["llm1_provider"] = provider
    s["llm1_model"]    = model_id
    s["llm2_provider"] = provider
    s["llm2_model"]    = model_id
    print(f"{GRAY}  Model override: {provider} / {model_id}{X}")


# ─────────────────────────────────────────────────────────────────────────────
# Strategy builders
# ─────────────────────────────────────────────────────────────────────────────

_strategy_cache = {}

def get_strategy(name: str):
    if name not in _strategy_cache:
        if name == "baseline":
            from strategies.baseline import BaselineStrategy
            _strategy_cache[name] = BaselineStrategy()
        elif name == "rag":
            from strategies.rag import RAGStrategy
            r = RAGStrategy()
            print(f"{GRAY}  Building RAG index…{X}")
            r.build_index()
            _strategy_cache[name] = r
        elif name == "formal":
            from strategies.formal import FormalStrategy
            _strategy_cache[name] = FormalStrategy()
        elif name == "agentic":
            from strategies.agentic import AgenticStrategy
            _strategy_cache[name] = AgenticStrategy()
    return _strategy_cache[name]


def run_one(question: str, strategy: str, verbose: bool = False,
            show_progress: bool = False) -> dict:
    s = get_strategy(strategy)
    # Pass progress_callback to strategies that support it (formal, agentic)
    sig = inspect.signature(s.run)
    if show_progress and "progress_callback" in sig.parameters:
        cb = lambda msg: _progress_printer(strategy, msg)
        res = s.run(question, progress_callback=cb)
    else:
        res = s.run(question)
    return {
        "strategy":       strategy,
        "verdict":        getattr(res, "verdict", "ERROR"),
        "citations":      getattr(res, "citations", []),
        "answer":         getattr(res, "answer", ""),
        "expl_tree":      getattr(res, "explanation_tree", ""),
        "latency":        getattr(res, "latency_seconds", 0),
        "error":          getattr(res, "error", getattr(res, "error_message", "")),
        "generated_facts":getattr(res, "generated_facts", "") if verbose else "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Print helpers
# ─────────────────────────────────────────────────────────────────────────────

def print_result(q: str, result: dict, verbose: bool = False):
    v   = result["verdict"]
    cit = ", ".join(result["citations"]) if result["citations"] else "—"
    color = G if v in ("ALLOWED","PERMITTED") else R if v in ("DENIED","NOT PERMITTED") else Y
    strat = result["strategy"].upper()

    print(f"\n{BOLD}[{strat}]{X} {color}{v}{X}  |  {B}{cit}{X}  |  ⏱ {result['latency']}s")
    if result["answer"]:
        print()
        for line in result["answer"].split("\n")[:15]:
            print(f"  {line}")
    if result["expl_tree"] and verbose:
        print(f"\n{GRAY}  Explanation tree:\n  {result['expl_tree']}{X}")
    if result["generated_facts"] and verbose:
        print(f"\n{GRAY}  Datalog facts:\n{result['generated_facts']}{X}")
    if result["error"] and v == "ERROR":
        print(f"\n{Y}  Error: {result['error'][:200]}{X}")


def print_comparison(q: str, results: list):
    print(f"\n{BOLD}{'='*62}{X}")
    print(f"{BOLD}QUESTION:{X} {q}")
    print(f"{BOLD}{'='*62}{X}")
    print(f"\n{'Strategy':<12} {'Verdict':<20} {'Citations':<35} {'Latency'}")
    print(f"{'─'*12} {'─'*20} {'─'*35} {'─'*8}")
    for r in results:
        v     = r["verdict"]
        color = G if v in ("ALLOWED","PERMITTED") else R if v in ("DENIED","NOT PERMITTED") else Y
        cit   = "; ".join(r["citations"][:3]) if r["citations"] else "—"
        print(f"{r['strategy']:<12} {color}{v:<20}{X} {cit:<35} {r['latency']}s")


# ─────────────────────────────────────────────────────────────────────────────
# Batch eval
# ─────────────────────────────────────────────────────────────────────────────

def normalize_verdict(v: str) -> str:
    v = v.strip().upper()
    if v in ("ALLOWED", "PERMITTED", "YES", "TRUE"):   return "PERMITTED"
    if v in ("DENIED", "NOT PERMITTED", "NO", "FALSE"): return "DENIED"
    return v


def run_benchmark(csv_path: str, strategies: list, output_path: str,
                  q_col: str = "question", a_col: str = "answer",
                  verbose: bool = False):
    print(f"\n{BOLD}BATCH EVAL{X}")
    print(f"  Input:      {csv_path}")
    print(f"  Strategies: {', '.join(strategies)}")
    print(f"  Output:     {output_path}\n")

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"  Loaded {len(rows)} rows from {csv_path}\n")

    # Pre-init strategies
    for strat in strategies:
        print(f"{GRAY}  Init {strat}…{X}")
        try:
            get_strategy(strat)
        except Exception as e:
            print(f"{Y}  Warning: could not init {strat}: {e}{X}")

    all_output = []
    totals = {s: {"correct": 0, "evaluated": 0, "errors": 0} for s in strategies}

    for i, row in enumerate(rows):
        question = row.get(q_col, "").strip()
        if not question:
            continue
        ground_raw = row.get(a_col, "").strip()
        ground     = normalize_verdict(ground_raw) if ground_raw else ""

        print(f"[{i+1:03d}/{len(rows)}] {question[:70]}…")

        for strat in strategies:
            try:
                result = run_one(question, strat, verbose)
                verdict_norm = normalize_verdict(result["verdict"])
                match = ""
                if ground:
                    match = "Y" if verdict_norm == ground else "N"
                    if result["verdict"] not in ("ERROR", "UNKNOWN"):
                        totals[strat]["evaluated"] += 1
                        if match == "Y":
                            totals[strat]["correct"] += 1
                    else:
                        totals[strat]["errors"] += 1

                icon  = G+"✓"+X if match == "Y" else R+"✗"+X if match == "N" else "·"
                color = G if result["verdict"] in ("ALLOWED","PERMITTED") else \
                        R if result["verdict"] in ("DENIED","NOT PERMITTED") else Y
                print(f"  {icon} [{strat}] {color}{result['verdict']}{X}  "
                      f"citations: {', '.join(result['citations'][:2]) or '—'}")

                out_row = {
                    **{k: v for k, v in row.items() if k not in (q_col, a_col)},
                    "question":       question,
                    "ground_truth":   ground,
                    "strategy":       strat,
                    "verdict":        result["verdict"],
                    "verdict_norm":   verdict_norm,
                    "match":          match,
                    "citations":      "; ".join(result["citations"]),
                    "latency_s":      result["latency"],
                    "llm_answer":     result["answer"][:400],
                    "explanation":    result["expl_tree"][:300],
                    "error":          result["error"][:200],
                    "timestamp":      datetime.now().isoformat(),
                }
                all_output.append(out_row)

            except Exception as e:
                print(f"  {Y}ERROR [{strat}]: {e}{X}")
                totals[strat]["errors"] += 1
                all_output.append({
                    "question": question, "strategy": strat, "verdict": "ERROR",
                    "error": str(e)[:200], "ground_truth": ground, "match": "",
                    "verdict_norm": "ERROR", "citations": "", "latency_s": 0,
                    "llm_answer": "", "explanation": "", "timestamp": datetime.now().isoformat(),
                })

    # Write output
    if all_output:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_output[0].keys()))
            writer.writeheader()
            writer.writerows(all_output)

    # Summary
    print(f"\n{BOLD}{'='*55}{X}")
    print(f"{BOLD}SUMMARY{X}")
    print(f"{'─'*55}")
    print(f"{'Strategy':<12} {'Correct':<10} {'Accuracy':<12} {'Errors'}")
    print(f"{'─'*12} {'─'*10} {'─'*12} {'─'*8}")
    for strat in strategies:
        ev  = totals[strat]["evaluated"]
        cor = totals[strat]["correct"]
        err = totals[strat]["errors"]
        acc = f"{cor/ev*100:.1f}%" if ev > 0 else "N/A"
        print(f"{strat:<12} {cor}/{ev:<8} {acc:<12} {err}")
    print(f"\n  Results saved → {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ComplianceGPT — HIPAA Compliance CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python app/cli.py -q "Can I see my lab results?"
  python app/cli.py -q "..." --strategy all
  python app/cli.py -q "..." --strategy baseline --model openai/gpt-4o
  python app/cli.py --benchmark data/benchmark.csv --strategy formal
  python app/cli.py --benchmark data/benchmark.csv --strategy all --output results.csv
        """,
    )
    parser.add_argument("-q", "--question",  help="Single question to check")
    parser.add_argument("--strategy",
                        default="formal",
                        help="Strategy: baseline|rag|formal|agentic|all (default: formal)")
    parser.add_argument("--model",
                        default=None,
                        help="Model override: provider/model-id (e.g. openai/gpt-4o)")
    parser.add_argument("--benchmark",       help="Path to benchmark CSV for batch eval")
    parser.add_argument("--output",          default="results.csv",
                        help="Output CSV path (batch eval, default: results.csv)")
    parser.add_argument("--question-col",    default=None,
                        help="CSV column for questions (default from settings)")
    parser.add_argument("--answer-col",      default=None,
                        help="CSV column for ground truth (default from settings)")
    parser.add_argument("-v", "--verbose",   action="store_true",
                        help="Show Datalog facts and explanation trees")
    parser.add_argument("--list-models",     action="store_true",
                        help="List all available models and exit")
    parser.add_argument("--plan",            action="store_true", default=True,
                        help="Auto-rephrase first-person / relational questions (default: on)")
    parser.add_argument("--no-plan",         action="store_true",
                        help="Disable question planning pre-processor")
    args = parser.parse_args()

    # ── List models ──────────────────────────────────────────────────────────
    if args.list_models:
        from connector.settings import MODEL_REGISTRY
        for provider, models in MODEL_REGISTRY.items():
            print(f"\n{BOLD}{provider.upper()}{X}")
            for m in models:
                print(f"  {B}{provider}/{m['id']}{X}  —  {m['label']}  {GRAY}[{m['notes']}]{X}")
        return

    # ── Apply model override ─────────────────────────────────────────────────
    if args.model:
        apply_model_override(args.model)

    # ── Resolve strategies ───────────────────────────────────────────────────
    strat_arg = args.strategy.lower()
    if strat_arg == "all":
        strategies = ["baseline", "rag", "formal", "agentic"]
    elif strat_arg in ("baseline", "rag", "formal", "agentic"):
        strategies = [strat_arg]
    else:
        print(f"{Y}Unknown strategy '{strat_arg}'. Use baseline|rag|formal|agentic|all{X}")
        sys.exit(1)

    use_planner = args.plan and not args.no_plan

    s = get_settings()
    q_col = args.question_col  or s["batch_question_col"]
    a_col = args.answer_col    or s["batch_answer_col"]

    # ── Batch eval ───────────────────────────────────────────────────────────
    if args.benchmark:
        run_benchmark(args.benchmark, strategies, args.output, q_col, a_col, args.verbose)
        return

    # ── Single question ──────────────────────────────────────────────────────
    if args.question:
        q = args.question

        # Planning phase — rephrase first-person / relational questions
        if use_planner:
            from connector.planner import QuestionPlanner
            plan = QuestionPlanner().plan(q)
            if plan["was_rephrased"]:
                print(f"\n{Y}[Planning]{X} Question rephrased for canonical extraction:")
                print(f"  {GRAY}Original:  {plan['original']}{X}")
                print(f"  {B}Canonical: {plan['rephrased']}{X}")
                q = plan["rephrased"]

        print(f"\n{BOLD}{'='*62}{X}")
        print(f"{BOLD}QUESTION:{X} {q}")
        print(f"{BOLD}{'='*62}{X}")

        show_progress = any(st in strategies for st in ("formal", "agentic"))
        if len(strategies) == 1:
            print(f"{B}Running {strategies[0]}…{X}")
            result = run_one(q, strategies[0], args.verbose, show_progress=show_progress)
            print_result(q, result, args.verbose)
        else:
            results = []
            for i, strat in enumerate(strategies, 1):
                print(f"\n{B}[{i}/{len(strategies)}] {strat}…{X}")
                results.append(run_one(q, strat, args.verbose,
                                       show_progress=strat in ("formal", "agentic")))
            print_comparison(q, results)
            if args.verbose:
                for r in results:
                    print_result(q, r, verbose=True)
        return

    # ── Interactive ───────────────────────────────────────────────────────────
    print(f"{BOLD}ComplianceGPT — Interactive Mode{X}")
    strat_display = ", ".join(strategies)
    plan_status   = "on" if use_planner else "off"
    print(f"{GRAY}Strategies: {strat_display}  |  Planning: {plan_status}  |  Ctrl+C to exit{X}\n")

    while True:
        try:
            q = input(f"{B}Question:{X} ").strip()
            if not q:
                continue

            # Planning phase
            if use_planner:
                from connector.planner import QuestionPlanner
                plan = QuestionPlanner().plan(q)
                if plan["was_rephrased"]:
                    print(f"{Y}[Planning]{X} Rephrased: {B}{plan['rephrased']}{X}")
                    q = plan["rephrased"]

            show_progress = any(st in strategies for st in ("formal", "agentic"))
            if len(strategies) == 1:
                result = run_one(q, strategies[0], args.verbose, show_progress=show_progress)
                print_result(q, result, args.verbose)
            else:
                results = [run_one(q, st, args.verbose,
                                   show_progress=st in ("formal", "agentic"))
                           for st in strategies]
                print_comparison(q, results)
        except KeyboardInterrupt:
            print(f"\n{GRAY}Goodbye.{X}")
            break
        except Exception as e:
            print(f"{Y}Error: {e}{X}")


if __name__ == "__main__":
    main()
