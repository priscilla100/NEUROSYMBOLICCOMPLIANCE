"""
app/batch_runner.py
────────────────────────────────────────────────────────────────────────────
Dedicated batch evaluation runner. Handles all three CSV formats:
  - Your QA benchmark (hipaa_qa.csv)
  - PrivacyCI (norm_type, case_content, ...)
  - GoldCoin (generate_HIPAA_type, generate_background, ...)
  - Any CSV with a question column (auto-detected or specified)

USAGE:

  # Auto-detect everything (recommended)
  python app/batch_runner.py --input data/hipaa_qa.csv

  # Use HuggingFace local model (SLURM cluster)
  python app/batch_runner.py --input data/hipaa_qa.csv \\
      --strategy baseline --model hf:meta-llama/Llama-3.1-8B-Instruct

  # Use Ollama (local, free)
  python app/batch_runner.py --input data/hipaa_qa.csv \\
      --strategy baseline --model ollama/llama3.2

  # Limit rows (useful for testing)
  python app/batch_runner.py --input data/hipaa_qa.csv --limit 10

  # Full run with all strategies, save results
  python app/batch_runner.py \\
      --input data/hipaa_qa.csv \\
      --strategy all \\
      --output results/hipaa_qa_results.csv \\
      --limit 50

MODEL FORMAT:
  --model ollama/llama3.2                           local Ollama
  --model hf:meta-llama/Llama-3.1-8B-Instruct      HF local (SLURM)
  --model huggingface:mistralai/Mistral-7B-Instruct HF API (rate-limited)
  --model openai/gpt-4o                             OpenAI API
  --model anthropic/claude-sonnet-4-6               Anthropic API

COLUMN AUTO-DETECTION:
  hipaa_qa.csv   → question_col="question", gt_col="answer"
  privacyci.csv  → question_col="case_content", gt_col="norm_type"
  goldcoin.csv   → question_col="generate_background", gt_col="generate_HIPAA_type"
  Any other CSV  → uses first column with "question" in name, or first column
"""

import sys, os, csv, json, time, argparse
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ANSI colours
G="\033[92m"; R="\033[91m"; Y="\033[93m"; B="\033[94m"
GRAY="\033[90m"; BOLD="\033[1m"; X="\033[0m"

from connector.dataset_loader import (
    load_dataset, describe_dataset, DatasetRow, normalize_gt
)
from connector.settings import get_settings
from connector.model_client import ModelClient


# ─────────────────────────────────────────────────────────────────────────────
# Model string parsing
# ─────────────────────────────────────────────────────────────────────────────

# run_benchmark.py sends model strings in two formats:
#   "ollama/llama3:latest"         → provider=ollama,  model=llama3:latest
#   "hf:meta-llama/Llama-3.1-8B"  → provider=hf,      model=meta-llama/Llama-3.1-8B
#
# The tricky part: HF model names contain "/" so we can't just split on "/".
# We disambiguate by checking if the string starts with a known provider prefix.

PROVIDER_ALIASES = {
    "hf":          "hf",
    "huggingface": "huggingface",
    "openai":      "openai",
    "anthropic":   "anthropic",
    "google":      "google",
    "ollama":      "ollama",
}

def parse_model_string(model_str: str) -> tuple[str, str]:
    """
    Parse 'provider:model' or 'provider/model' into (provider, model_id).

    Examples
    --------
    "ollama/llama3:latest"                  → ("ollama",  "llama3:latest")
    "hf:meta-llama/Llama-3.1-8B-Instruct"  → ("hf",      "meta-llama/Llama-3.1-8B-Instruct")
    "huggingface:mistralai/Mistral-7B"      → ("huggingface", "mistralai/Mistral-7B")
    "openai/gpt-4o"                         → ("openai",  "gpt-4o")
    "anthropic/claude-sonnet-4-6"           → ("anthropic","claude-sonnet-4-6")
    """
    # Check colon-prefixed providers first (hf:org/model, huggingface:org/model)
    for prefix in ("hf:", "huggingface:", "openai:", "anthropic:", "google:", "ollama:"):
        if model_str.startswith(prefix):
            provider_raw = prefix.rstrip(":")
            model_id     = model_str[len(prefix):]
            return PROVIDER_ALIASES.get(provider_raw, provider_raw), model_id

    # Slash-prefixed providers — only safe when provider has no slash in its name
    # and the model portion doesn't look like an HF org/model path.
    if "/" in model_str:
        provider_raw, _, model_id = model_str.partition("/")
        if provider_raw.lower() in PROVIDER_ALIASES:
            return PROVIDER_ALIASES[provider_raw.lower()], model_id

    # No recognisable prefix — treat entire string as an Ollama model name
    return "ollama", model_str


# ─────────────────────────────────────────────────────────────────────────────
# Strategy runners
# ─────────────────────────────────────────────────────────────────────────────

_strategy_cache: dict[str, object] = {}

def get_strategy(name: str, model_override: str = None):
    """
    Return a cached strategy instance.

    Cache key includes model so switching models mid-run still works,
    but within a single batch job the same strategy+model is reused for
    every row — avoiding repeated ModelClient / model weight initialisation.
    """
    key = f"{name}:{model_override or '__default__'}"
    if key in _strategy_cache:
        return _strategy_cache[key]

    s = get_settings()

    if model_override:
        provider, model_id = parse_model_string(model_override)
        if provider not in ModelClient.SUPPORTED:
            raise ValueError(f"Unknown provider '{provider}'. Supported: {ModelClient.SUPPORTED}")
        s["llm1_provider"] = provider
        s["llm1_model"]    = model_id
        s["llm2_provider"] = provider
        s["llm2_model"]    = model_id

    # ── Prompt-style variants ─────────────────────────────────────────────────
    _PROMPT_STYLE_MAP = {
        "baseline_fs":    ("baseline", "few_shot"),
        "baseline_cot":   ("baseline", "cot"),
        "baseline_fscot": ("baseline", "few_shot_cot"),
        "rag_fs":         ("rag",      "few_shot"),
        "rag_cot":        ("rag",      "cot"),
        "rag_fscot":      ("rag",      "few_shot_cot"),
    }

    if name in _PROMPT_STYLE_MAP:
        base, style = _PROMPT_STYLE_MAP[name]
        if base == "baseline":
            from strategies.baseline import BaselineStrategy
            _strategy_cache[key] = BaselineStrategy(prompt_style=style)
        elif base == "rag":
            from strategies.rag import RAGStrategy
            r = RAGStrategy(prompt_style=style)
            print(f"{GRAY}  Building RAG index ({name})…{X}")
            try:
                r.build_index()
            except Exception as e:
                err_msg = str(e)
                if any(x in err_msg.lower() for x in [
                    "connection", "timeout", "404", "no such file",
                    "model not found", "oserror", "httperror", "urlopen",
                ]):
                    print(f"\n{R}  RAG build_index failed — embedding model not in cache.{X}")
                    print(f"{Y}  Fix: run once on a login node (internet access):{X}")
                    print(f"    python -c \"from sentence_transformers import SentenceTransformer; "
                          f"SentenceTransformer('all-MiniLM-L6-v2')\"")
                raise RuntimeError(f"RAG build_index failed: {err_msg}") from e
            _strategy_cache[key] = r
        return _strategy_cache[key]

    # ── Core strategies ───────────────────────────────────────────────────────
    if name == "baseline":
        from strategies.baseline import BaselineStrategy
        _strategy_cache[key] = BaselineStrategy()

    elif name == "rag":
        from strategies.rag import RAGStrategy
        r = RAGStrategy()
        print(f"{GRAY}  Building RAG index…{X}")
        try:
            r.build_index()
        except Exception as e:
            err_msg = str(e)
            if any(x in err_msg.lower() for x in [
                "connection", "timeout", "404", "no such file",
                "model not found", "oserror", "httperror", "urlopen",
            ]):
                print(f"\n{R}  RAG build_index failed — embedding model not in cache.{X}")
                print(f"{Y}  Fix: run once on a login node (internet access):{X}")
                print(f"    python -c \"from sentence_transformers import SentenceTransformer; "
                      f"SentenceTransformer('all-MiniLM-L6-v2')\"")
                print(f"{Y}  Compute nodes read from HF_CACHE_DIR — no internet after that.{X}")
                print(f"{Y}  Or skip RAG on the cluster: --strategies baseline formal{X}\n")
            raise RuntimeError(f"RAG build_index failed: {err_msg}") from e
        _strategy_cache[key] = r

    elif name == "formal":
        from strategies.formal import FormalStrategy
        _strategy_cache[key] = FormalStrategy()

    elif name == "agentic":
        from strategies.agentic import AgenticStrategy
        _strategy_cache[key] = AgenticStrategy()

    else:
        raise ValueError(f"Unknown strategy: {name}")

    return _strategy_cache[key]


def run_one(row: DatasetRow, strategy: str, model_override: str = None) -> dict:
    t0 = time.time()
    try:
        strat = get_strategy(strategy, model_override)
        res   = strat.run(row.question)
        v     = getattr(res, "verdict", "ERROR")
        nv    = norm_verdict(v)
        cit   = getattr(res, "citations", [])
        ans   = getattr(res, "answer", "")[:500]
        expl  = getattr(res, "explanation_tree", "")[:300]
        err   = getattr(res, "error", getattr(res, "error_message", ""))[:200]

        # ── Infer citations for denied verdicts (HIPAA) ───────────────────────
        _scen = getattr(res, "scenario", None)
        _attr = getattr(_scen, "attribute", "") or ""
        _purp = getattr(_scen, "purpose",   "") or ""
        _reg  = get_settings().get("active_regulation", "hipaa")
        if not cit and nv == "DENIED" and _reg == "hipaa":
            if _purp == "marketing":
                cit = ["164.508", "164.508(a)(3)"]
            elif _attr == "psychotherapy-notes":
                cit = ["164.508", "164.508(a)(2)"]
            elif _attr in ("genetic-info",):
                cit = ["164.502", "164.502(a)(5)(i)"]
            elif _purp in ("sale-of-phi", "sale"):
                cit = ["164.502", "164.502(a)(5)(ii)", "164.508"]
            elif _attr == "substance-abuse-records":
                cit = ["164.502", "164.508"]
            elif _purp == "marketing" or "employer" in (ans + expl).lower():
                cit = ["164.502", "164.502(a)(5)"]
            else:
                cit = ["164.502", "164.502(b)"] if "minimum" in (ans + expl).lower() \
                      else ["164.502"]

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise

    match = ""
    if row.is_labeled():
        match = "Y" if nv == row.ground_truth else "N"

    return {
        "row_id":       row.row_id,
        "format":       row.format,
        "topic":        row.topic,
        "complexity":   row.complexity,
        "regulation":   row.regulation,
        "question":     row.question[:300],
        "ground_truth": row.ground_truth,
        "strategy":     strategy,
        "model":        model_override or f"{get_settings()['llm1_provider']}/{get_settings()['llm1_model']}",
        "verdict":      nv,
        "verdict_norm": nv,
        "match":        match,
        "citations":    "; ".join(cit),
        "latency_s":    round(time.time() - t0, 2),
        "llm_answer":    ans,
        "explanation":   expl,
        "scenario_json": getattr(res, "scenario_json", ""),
        "llm_raw":       getattr(res, "llm_raw", ""),
        "error":         err,
        "timestamp":     datetime.now().isoformat(),
    }


def norm_verdict(v: str) -> str:
    if v in ("ALLOWED", "PERMITTED"):    return "PERMITTED"
    if v in ("DENIED", "NOT PERMITTED"): return "DENIED"
    return v


# ─────────────────────────────────────────────────────────────────────────────
# Main batch runner
# ─────────────────────────────────────────────────────────────────────────────

def run_batch(
    input_path:     str,
    strategies:     list,
    output_path:    str,
    question_col:   str   = None,
    answer_col:     str   = None,
    model_override: str   = None,
    limit:          int   = None,
    start:          int   = 1,
    verbose:        bool  = False,
    row_delay:      float = 0.0,   # extra sleep between rows (on top of model_client delay)
):
    print(f"\n{BOLD}ComplianceGPT Batch Runner{X}")
    print(f"  Input:      {input_path}")
    print(f"  Strategies: {', '.join(strategies)}")
    print(f"  Model:      {model_override or 'from settings'}")
    if limit:     print(f"  Limit:      {limit} rows")
    if row_delay: print(f"  Row delay:  {row_delay}s")
    print()

    rows = load_dataset(input_path, question_col, answer_col)
    if not rows:
        print(f"{R}No rows loaded.{X}")
        return

    rows = rows[start - 1:]
    if limit:
        rows = rows[:limit]

    desc = describe_dataset(rows)
    print(f"  Loaded {desc['total']} rows  "
          f"(labeled: {desc['labeled']}  |  "
          f"permitted: {desc['permitted']}  |  "
          f"denied: {desc['denied']}  |  "
          f"format: {list(desc['formats'].keys())})")
    print()

    # ── Initialise strategies once, before the row loop ───────────────────────
    for strat in strategies:
        print(f"{GRAY}  Init {strat}…{X}")
        try:
            get_strategy(strat, model_override)
            print(f"  {G}✓ {strat} ready{X}")
        except Exception as e:
            print(f"  {R}✗ {strat} failed: {e}{X}")
    print()

    # ── Open output CSV (crash-safe: flush after every row) ───────────────────
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    RESULT_FIELDS = [
        "row_id", "format", "topic", "complexity", "regulation",
        "question", "ground_truth", "strategy", "model",
        "verdict", "verdict_norm", "match", "citations",
        "latency_s", "llm_answer", "explanation",
        "scenario_json", "llm_raw",
        "error", "timestamp",
    ]
    out_file   = open(output_path, "w", newline="", encoding="utf-8")
    csv_writer = csv.DictWriter(out_file, fieldnames=RESULT_FIELDS)
    csv_writer.writeheader()
    out_file.flush()

    # ── Row loop ──────────────────────────────────────────────────────────────
    all_results = []
    totals      = {s: {"ok": 0, "ev": 0, "err": 0} for s in strategies}

    try:
        for i, row in enumerate(rows):
            short_q = row.question[:70].replace("\n", " ")
            print(f"{BOLD}[{i+1:03d}/{len(rows)}]{X} {short_q}{'…' if len(row.question) > 70 else ''}")

            for strat in strategies:
                result = run_one(row, strat, model_override)
                v      = result["verdict"]
                nv     = result["verdict_norm"]
                match  = result["match"]
                lat    = result["latency_s"]
                cits   = result["citations"][:40]

                if v in ("ERROR", "UNKNOWN"):
                    totals[strat]["err"] += 1
                elif match == "Y":
                    totals[strat]["ev"] += 1
                    totals[strat]["ok"] += 1
                elif match == "N":
                    totals[strat]["ev"] += 1

                v_color = G if nv == "PERMITTED" else R if nv == "DENIED" else Y
                m_icon  = f"{G}✓{X}" if match == "Y" else f"{R}✗{X}" if match == "N" else "·"
                gt_str  = f" (gt={row.ground_truth})" if row.is_labeled() else ""

                print(f"  {m_icon} [{strat:8s}] {v_color}{nv:12s}{X}  "
                      f"{B}{cits[:35]}{X}  ⏱{lat}s{gt_str}")

                if verbose and result["llm_answer"]:
                    for line in result["llm_answer"].split("\n")[:3]:
                        print(f"    {GRAY}{line[:100]}{X}")

                csv_writer.writerow(result)
                out_file.flush()
                all_results.append(result)

            # Optional extra delay between rows (separate from model_client delay)
            if row_delay > 0:
                time.sleep(row_delay)

            print()
    finally:
        out_file.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'='*60}{X}")
    print(f"{BOLD}SUMMARY{X}")
    print(f"{'─'*60}")
    print(f"{'Strategy':<12} {'Model':<30} {'Correct':<10} {'Accuracy':<12} {'Errors'}")
    print(f"{'─'*12} {'─'*30} {'─'*10} {'─'*12} {'─'*6}")

    for strat in strategies:
        ev  = totals[strat]["ev"]
        ok  = totals[strat]["ok"]
        err = totals[strat]["err"]
        acc = f"{ok/ev*100:.1f}%" if ev > 0 else "N/A"
        _s  = get_settings()
        mod = (model_override or f"{_s['llm1_provider']}/{_s['llm1_model']}")[:29]
        print(f"{strat:<12} {mod:<30} {ok}/{ev:<8} {acc:<12} {err}")

    print(f"\n  Results → {output_path}")
    print(f"  Total rows processed: {len(rows)} × {len(strategies)} = {len(all_results)} evaluations")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ComplianceGPT Batch Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", "-i",     required=True, help="Path to input CSV")
    parser.add_argument("--strategy", "-s",  default="formal",
                        help="Strategy: baseline|rag|formal|agentic|all (default: formal)")
    parser.add_argument("--model", "-m",     default=None,
                        help=(
                            "Model: provider/model or provider:model. "
                            "e.g. ollama/llama3.2  |  hf:meta-llama/Llama-3.1-8B-Instruct  |  openai/gpt-4o"
                        ))
    parser.add_argument("--output", "-o",    default=None,
                        help="Output CSV path (default: results/<input_stem>_results.csv)")
    parser.add_argument("--question-col",    default=None,
                        help="Column name for questions (auto-detected if not set)")
    parser.add_argument("--answer-col",      default=None,
                        help="Column name for ground truth (auto-detected if not set)")
    parser.add_argument("--limit", "-n",     type=int, default=None,
                        help="Max rows to process")
    parser.add_argument("--start",           type=int, default=1,
                        help="Start from row N (1-indexed, default: 1)")
    parser.add_argument("--verbose", "-v",   action="store_true",
                        help="Print LLM answer snippets")
    parser.add_argument("--preview",         action="store_true",
                        help="Print dataset preview and exit (no evaluation)")
    parser.add_argument("--regulation",      default=None,
                        choices=["hipaa", "gdpr", "glba", "ccpa", "coppa", "sox"],
                        help="Set active regulation before running (saved to settings)")
    parser.add_argument("--delay",           type=float, default=0.0,
                        help=(
                            "Extra sleep (seconds) between rows, on top of the "
                            "model_client inter-call delay. Useful when you need "
                            "additional pacing beyond what the model tier sets. "
                            "Default: 0 (model_client handles its own delay)."
                        ))
    args = parser.parse_args()

    # Apply regulation override BEFORE initialising strategies
    if args.regulation:
        s = get_settings()
        s["active_regulation"] = args.regulation
        s.save()

    # Resolve strategies
    _VALID = {
        "baseline", "rag", "formal", "agentic",
        "baseline_fs", "baseline_cot", "baseline_fscot",
        "rag_fs",      "rag_cot",      "rag_fscot",
    }
    strat_arg = args.strategy.lower()
    if strat_arg == "all":
        strategies = ["baseline", "rag", "formal", "agentic"]
    elif strat_arg in _VALID:
        strategies = [strat_arg]
    else:
        print(f"{R}Unknown strategy '{strat_arg}'. Valid: {sorted(_VALID)}{X}")
        sys.exit(1)

    # Resolve output path
    if args.output:
        output_path = args.output
    else:
        stem = Path(args.input).stem
        output_path = str(
            Path("results") / f"{stem}_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

    # Preview mode
    if args.preview:
        rows = load_dataset(args.input, args.question_col, args.answer_col)
        desc = describe_dataset(rows)
        print(f"\n{BOLD}Dataset Preview: {args.input}{X}")
        print(f"  Format:    {list(desc['formats'].keys())}")
        print(f"  Total:     {desc['total']}")
        print(f"  Labeled:   {desc['labeled']} (permitted={desc['permitted']}, denied={desc['denied']})")
        print(f"  Unlabeled: {desc['unlabeled']}")
        print(f"\n  First 3 questions:")
        for r in rows[:3]:
            print(f"  [{r.row_id}] [{r.ground_truth or '?'}] {r.question[:100]}…")
        return

    run_batch(
        input_path     = args.input,
        strategies     = strategies,
        output_path    = output_path,
        question_col   = args.question_col,
        answer_col     = args.answer_col,
        model_override = args.model,
        limit          = args.limit,
        start          = args.start,
        verbose        = args.verbose,
        row_delay      = args.delay,
    )


if __name__ == "__main__":
    main()