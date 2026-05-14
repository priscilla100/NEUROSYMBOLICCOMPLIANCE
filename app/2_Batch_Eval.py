"""
app/pages/2_Batch_Eval.py
─────────────────────────────────────────────────────────────────────────────
Batch evaluation page.
Upload a CSV → pick strategies → run → download results CSV.

Expected CSV columns (configurable in Settings):
  question   — natural language HIPAA question
  answer     — ground truth: "Yes"/"No"/"Permitted"/"Denied" (optional)

Optional columns (passed through to output):
  id, topic, complexity, regulation, explanation, cross_references
"""

import sys, os, io, csv, time, json
from pathlib import Path
from datetime import datetime
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from connector.settings import get_settings

st.set_page_config(page_title="Batch Eval — ComplianceGPT", page_icon="📊", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background: #ffffff !important; }
[data-testid="stSidebar"] { background: #f8f9fa !important; border-right: 1px solid #dee2e6; }
h1, h2, h3 { color: #1a1a2e; }
p, li, label, [data-testid="stMarkdownContainer"] p { color: #212529; }
.stButton > button { background: #0d6efd !important; color: #fff !important;
    border: none !important; border-radius: 6px !important;
    font-family: 'IBM Plex Mono', monospace !important; font-weight: 600 !important; }
.stButton > button:hover { background: #0b5ed7 !important; }
hr { border-color: #dee2e6 !important; }
.pill { display: inline-block; background: #e7f1ff; border: 1px solid #b6d4fe;
        border-radius: 12px; padding: 1px 9px; font-family: 'IBM Plex Mono', monospace;
        font-size: 0.72rem; color: #0a58ca; margin: 2px; }
.stat-box { border: 1px solid #dee2e6; border-radius: 8px; padding: 16px;
            text-align: center; background: #f8f9fa; }
.stat-num { font-family: 'IBM Plex Mono', monospace; font-size: 2rem;
            font-weight: 700; color: #1a1a2e; }
.stat-label { color: #6c757d; font-size: 0.8rem; margin-top: 2px; }
.progress-row { font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem;
                padding: 4px 0; border-bottom: 1px solid #f1f3f5; }
.row-ok  { color: #198754; }
.row-err { color: #dc3545; }
</style>
""", unsafe_allow_html=True)

s = get_settings()


def normalize_verdict(v: str) -> str:
    v = v.strip().upper()
    if v in ("ALLOWED", "PERMITTED", "YES", "TRUE"):  return "PERMITTED"
    if v in ("DENIED", "NOT PERMITTED", "NO", "FALSE"): return "DENIED"
    return v


def run_single_row(question: str, strategy: str, strategies_cache: dict) -> dict:
    """Run one question through one strategy. Returns result dict."""
    t0 = time.time()
    try:
        if strategy == "baseline":
            res = strategies_cache["baseline"].run(question)
        elif strategy == "rag":
            res = strategies_cache["rag"].run(question)
        elif strategy == "formal":
            res = strategies_cache["formal"].run(question)
        elif strategy == "agentic":
            res = strategies_cache["agentic"].run(question)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        return {
            "verdict":          getattr(res, "verdict", "ERROR"),
            "citations":        "; ".join(getattr(res, "citations", [])),
            "explanation_tree": getattr(res, "explanation_tree", "")[:300],
            "llm_answer":       getattr(res, "answer", "")[:500],
            "latency":          round(time.time() - t0, 2),
            "error":            getattr(res, "error", getattr(res, "error_message", "")),
        }
    except Exception as e:
        return {
            "verdict": "ERROR", "citations": "", "explanation_tree": "",
            "llm_answer": "", "latency": round(time.time() - t0, 2), "error": str(e)[:200],
        }


def results_to_csv_bytes(rows: list) -> bytes:
    if not rows:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Page layout
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("# 📊 Batch Evaluation")
st.markdown("Upload a CSV of HIPAA questions, run one or more strategies, download results.")
st.divider()

# ── Step 1: Upload ────────────────────────────────────────────────────────────
st.markdown("## Step 1 — Upload CSV")

col_up, col_format = st.columns([2, 1])
with col_up:
    uploaded = st.file_uploader(
        "Upload your benchmark CSV",
        type=["csv"],
        key="batch_upload",
    )

with col_format:
    st.markdown("**Expected columns:**")
    st.markdown("""
    - `question` *(required)*
    - `answer` — ground truth Yes/No *(optional)*
    - `id`, `topic`, `complexity` *(optional, passed through)*
    """)

if uploaded:
    try:
        content = uploaded.read().decode("utf-8", errors="replace")
        rows = list(csv.DictReader(io.StringIO(content)))
        if not rows:
            st.error("CSV is empty.")
            st.stop()
        st.success(f"✓ Loaded {len(rows)} rows. Columns: {', '.join(rows[0].keys())}")
    except Exception as e:
        st.error(f"Could not parse CSV: {e}")
        st.stop()

    # Column mapping
    st.markdown("**Column mapping:**")
    all_cols = list(rows[0].keys())
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        q_col = st.selectbox("Question column",
                             options=all_cols,
                             index=all_cols.index(s["batch_question_col"])
                             if s["batch_question_col"] in all_cols else 0)
    with col_m2:
        has_gt = any(k.lower() in ("answer", "verdict", "ground_truth", "label") for k in all_cols)
        a_col_options = ["(none)"] + all_cols
        a_col_default = s["batch_answer_col"] if s["batch_answer_col"] in all_cols else "(none)"
        a_col = st.selectbox("Ground truth column (optional)",
                             options=a_col_options,
                             index=a_col_options.index(a_col_default))

    # Preview
    with st.expander(f"Preview (first 5 of {len(rows)} rows)"):
        preview_rows = rows[:5]
        st.table([{q_col: r.get(q_col, ""), a_col if a_col != "(none)" else "—":
                   r.get(a_col, "") if a_col != "(none)" else "—"} for r in preview_rows])

    st.divider()

    # ── Step 2: Configure ─────────────────────────────────────────────────────
    st.markdown("## Step 2 — Configure Run")

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        strategies_to_run = st.multiselect(
            "Strategies to run",
            options=["baseline", "rag", "formal", "agentic"],
            default=[s["batch_strategy"]],
        )
    with col_s2:
        start_row = st.number_input("Start from row", min_value=1, max_value=len(rows), value=1)
        end_row   = st.number_input("End at row (inclusive)", min_value=1,
                                    max_value=len(rows), value=min(len(rows), 50))
    with col_s3:
        st.markdown("**Current models:**")
        p1, m1 = s.effective_llm1_model()
        p2, m2 = s.effective_llm2_model()
        st.markdown(f"`LLM1` {p1} / {m1}")
        st.markdown(f"`LLM2` {p2} / {m2}")
        st.markdown("*Change in Settings page*")

    rows_to_run = rows[start_row - 1 : end_row]
    st.caption(f"Will process {len(rows_to_run)} rows × {len(strategies_to_run)} strategies "
               f"= {len(rows_to_run) * len(strategies_to_run)} total calls")

    st.divider()

    # ── Step 3: Run ───────────────────────────────────────────────────────────
    st.markdown("## Step 3 — Run")

    if "batch_results" not in st.session_state:
        st.session_state["batch_results"] = []
    if "batch_running" not in st.session_state:
        st.session_state["batch_running"] = False

    col_run, col_stop = st.columns([2, 1])
    with col_run:
        run_btn = st.button(
            f"▶  Run {len(rows_to_run)} × {len(strategies_to_run) or 1} evaluations",
            use_container_width=True,
            disabled=not strategies_to_run,
        )
    with col_stop:
        st.markdown("")  # spacing

    if run_btn and strategies_to_run:
        st.session_state["batch_results"] = []
        st.session_state["batch_running"] = True

        # Init strategies
        strategies_cache = {}
        with st.spinner("Initializing strategies…"):
            for strat in strategies_to_run:
                try:
                    if strat == "baseline":
                        from strategies.baseline import BaselineStrategy
                        strategies_cache["baseline"] = BaselineStrategy()
                    elif strat == "rag":
                        from strategies.rag import RAGStrategy
                        r = RAGStrategy()
                        r.build_index()
                        strategies_cache["rag"] = r
                    elif strat == "formal":
                        from strategies.formal import FormalStrategy
                        strategies_cache["formal"] = FormalStrategy()
                    elif strat == "agentic":
                        from strategies.agentic import AgenticStrategy
                        strategies_cache["agentic"] = AgenticStrategy()
                except Exception as e:
                    st.error(f"Failed to init {strat}: {e}")

        # Progress UI
        progress_bar   = st.progress(0.0)
        status_text    = st.empty()
        log_container  = st.container()

        all_output_rows = []
        total_steps     = len(rows_to_run) * len(strategies_to_run)
        step            = 0
        correct         = {strat: 0 for strat in strategies_to_run}
        evaluated       = {strat: 0 for strat in strategies_to_run}

        for i, row in enumerate(rows_to_run):
            question   = row.get(q_col, "").strip()
            ground_raw = row.get(a_col, "") if a_col != "(none)" else ""
            ground     = normalize_verdict(ground_raw) if ground_raw else ""

            if not question:
                step += len(strategies_to_run)
                progress_bar.progress(min(step / total_steps, 1.0))
                continue

            for strat in strategies_to_run:
                step += 1
                progress_bar.progress(min(step / total_steps, 1.0))
                status_text.markdown(
                    f'`[{step}/{total_steps}]` Row {start_row + i} — strategy **{strat}** — `{question[:60]}…`'
                )

                result = run_single_row(question, strat, strategies_cache)
                verdict_norm = normalize_verdict(result["verdict"])

                match = ""
                if ground:
                    match = "Y" if verdict_norm == ground else "N"
                    if result["verdict"] not in ("ERROR", "UNKNOWN"):
                        evaluated[strat] += 1
                        if match == "Y":
                            correct[strat] += 1

                output_row = {
                    # Passthrough
                    **{k: row.get(k, "") for k in row if k not in (q_col, a_col)},
                    # Core
                    "question":       question,
                    "ground_truth":   ground,
                    "strategy":       strat,
                    "verdict":        result["verdict"],
                    "verdict_norm":   verdict_norm,
                    "match":          match,
                    "citations":      result["citations"],
                    "latency_s":      result["latency"],
                    "llm_answer":     result["llm_answer"],
                    "explanation":    result["explanation_tree"],
                    "error":          result["error"],
                    "timestamp":      datetime.now().isoformat(),
                }
                all_output_rows.append(output_row)

                # Log line
                icon = "✓" if match == "Y" else "✗" if match == "N" else "·"
                color_class = "row-ok" if match == "Y" else "row-err" if match == "N" else ""
                with log_container:
                    st.markdown(
                        f'<div class="progress-row {color_class}">'
                        f'{icon} [{strat}] Row {start_row+i} — '
                        f'{result["verdict"]} — {result["latency"]}s</div>',
                        unsafe_allow_html=True
                    )

        st.session_state["batch_results"] = all_output_rows
        st.session_state["batch_running"] = False
        status_text.markdown("**✓ Run complete**")
        progress_bar.progress(1.0)

        # Accuracy summary
        if any(evaluated[s] > 0 for s in strategies_to_run):
            st.markdown("### Accuracy Summary")
            acc_cols = st.columns(len(strategies_to_run))
            for i, strat in enumerate(strategies_to_run):
                ev = evaluated[strat]
                cor = correct[strat]
                acc = f"{cor/ev*100:.1f}%" if ev > 0 else "N/A"
                with acc_cols[i]:
                    st.markdown(
                        f'<div class="stat-box"><div class="stat-num">{acc}</div>'
                        f'<div class="stat-label">{strat}<br>{cor}/{ev} correct</div></div>',
                        unsafe_allow_html=True
                    )

    # ── Step 4: Download ──────────────────────────────────────────────────────
    results = st.session_state.get("batch_results", [])
    if results:
        st.divider()
        st.markdown("## Step 4 — Download Results")

        total_r = len(results)
        permitted = sum(1 for r in results if normalize_verdict(r.get("verdict","")) == "PERMITTED")
        denied    = sum(1 for r in results if normalize_verdict(r.get("verdict","")) == "DENIED")
        errors    = sum(1 for r in results if r.get("verdict","") in ("ERROR","UNKNOWN"))
        matched   = sum(1 for r in results if r.get("match") == "Y")
        with_gt   = sum(1 for r in results if r.get("match") in ("Y","N"))

        c1, c2, c3, c4, c5 = st.columns(5)
        def stat(col, num, label):
            col.markdown(f'<div class="stat-box"><div class="stat-num">{num}</div>'
                         f'<div class="stat-label">{label}</div></div>', unsafe_allow_html=True)
        stat(c1, total_r, "Total")
        stat(c2, permitted, "Permitted")
        stat(c3, denied, "Denied")
        stat(c4, errors, "Errors")
        if with_gt:
            stat(c5, f"{matched/with_gt*100:.1f}%", f"Accuracy\n({matched}/{with_gt})")

        csv_bytes = results_to_csv_bytes(results)
        filename  = f"compliancegpt_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        st.download_button(
            label="⬇  Download Results CSV",
            data=csv_bytes,
            file_name=filename,
            mime="text/csv",
            use_container_width=True,
        )

        with st.expander(f"Preview results ({min(10, len(results))} rows)"):
            preview_cols = ["question", "strategy", "verdict", "match", "citations", "latency_s"]
            preview_data = [{k: r.get(k, "") for k in preview_cols} for r in results[:10]]
            st.table(preview_data)

else:
    st.info("Upload a CSV above to get started.")

st.divider()

# ── CLI reference ─────────────────────────────────────────────────────────────
st.markdown("## 💻 Command-Line Equivalent")
st.markdown("The same batch eval is available from the terminal:")
st.code("""
# Run batch eval with formal strategy
python app/cli.py \\
    --benchmark data/your_benchmark.csv \\
    --strategy formal \\
    --output results.csv

# Run all four strategies
python app/cli.py \\
    --benchmark data/benchmark.csv \\
    --strategy all \\
    --output results_all.csv

# Single question, specific strategy and model
python app/cli.py \\
    -q "Can a nurse report suspected child abuse to authorities?" \\
    --strategy baseline \\
    --model openai/gpt-4o
""", language="bash")
