# ComplianceGPT

End-to-end benchmark and interactive tool for evaluating LLM accuracy on privacy-regulation compliance questions. Supports six regulations (HIPAA, GDPR, GLBA, CCPA, COPPA, SOX), ten strategies (four prompt-engineering ablations × two bases + formal + agentic), three inference backends (Anthropic, Ollama, HuggingFace), and a three-component evaluation suite.

---

## Table of Contents

1. [Setup](#1-setup)
2. [One Command — Full Run](#2-one-command--full-run)
3. [Streamlit Web UI](#3-streamlit-web-ui)
4. [CLI — Single Questions & Interactive](#4-cli--single-questions--interactive)
5. [Batch Runner](#5-batch-runner-appbatch_runnerpy)
6. [Benchmark Runner](#6-benchmark-runner-run_benchmarkpy)
7. [Soufflé Engine — Direct](#7-soufflé-engine--direct)
8. [Python API — Direct Strategy Use](#8-python-api--direct-strategy-use)
9. [Evaluation Scripts](#9-evaluation-scripts)
10. [Datasets](#10-datasets)
11. [Strategies](#11-strategies)
12. [Models](#12-models)
13. [Regulations](#13-regulations)
14. [Output Files](#14-output-files)
15. [Settings Reference](#15-settings-reference)
16. [Repository Structure](#16-repository-structure)
17. [Troubleshooting](#17-troubleshooting)

---

## 1. Setup

### One-command setup (recommended)

```bash
bash setup.sh              # installs Python deps + Soufflé + creates default settings
bash setup.sh --check      # diagnose only (no changes)
bash setup.sh --pull-models  # also pull all 13 Ollama models (~333 GB total)
```

### Manual setup

```bash
# Python dependencies
pip install -r requirements.txt

# Soufflé (required for formal + agentic strategies)
brew install souffle-lang/souffle/souffle   # macOS
sudo apt-get install souffle               # Ubuntu/Debian
# Other: https://souffle-lang.github.io/install

# Local LLMs via Ollama (free, no API key)
brew install ollama
ollama serve                          # keep running in a separate terminal
ollama pull llama3.2:latest           # small model for testing
ollama pull llama3.3:70b-instruct-q4_0  # large model for formal strategy

# API keys (set whichever provider(s) you want to use)
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GOOGLE_API_KEY=...
export HUGGINGFACE_API_KEY=hf_...
```

### Verify everything is ready

```bash
bash setup.sh --check
souffle --version
ollama list
python -c "from connector.settings import get_settings; print('OK')"
```

---

## 2. One Command — Full Run

```bash
bash run_ablation.sh
```

This single command runs:
1. **Ollama benchmark** — all 13 models × 10 strategies × 2 HIPAA datasets (`goldcoin`, `hipaa_qa`)
2. **Component 1** — Soufflé engine isolation on all 107 GoldCoin rows (oracle facts, no LLM1)
3. **Component 2** — LLM2 faithfulness scoring on Component 1 outputs
4. **Component 3** — Full end-to-end pipeline (Ollama LLM1 + Soufflé + Ollama LLM2), 107 rows
5. **LLM1 field-level eval** — extraction accuracy vs `generate_characteristics` gold standard
6. **LLM2 faithfulness eval** — on the Ollama benchmark results
7. **Model-swap ablation** — Component 3 re-run with 7 LLM1/LLM2 combinations (same-model pairs + cross-model pairs)

All steps use Ollama by default — no API key required. To use Claude for component evals instead:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
LLM1_MODEL=anthropic/claude-sonnet-4-6 bash run_ablation.sh
```

**Safe to interrupt and resume:**
```bash
bash run_ablation.sh    # resume — already-completed CSVs are skipped
```

**Prerequisites before running:**
- Ollama is running (`ollama serve` in a separate terminal)
- Models are pulled (`ollama list` to check; pull missing with `ollama pull <model>`)
- Soufflé is installed (`souffle --version`)

---

## 3. Streamlit Web UI

```bash
streamlit run app/streamlit_app.py
# Opens at http://localhost:8501
```

### Pages

| Page | How to reach | What it does |
|---|---|---|
| **Compliance Checker** | Default landing page | Ask a natural-language question, pick regulation + strategy/ies, see verdict + citations + proof tree |
| **Methodology** | Sidebar → Methodology | Explains all four strategies and their design tradeoffs |
| **Settings** | Sidebar → Settings | Configure LLM provider/model, Soufflé path, RAG parameters, active regulation |
| **Batch Eval** | Sidebar → Batch Eval | Upload any CSV and run bulk evaluation from the browser |

### Compliance Checker inputs

| Input | Options |
|---|---|
| Question text | Any natural-language compliance question |
| Regulation | HIPAA, GDPR, GLBA, CCPA, COPPA, SOX |
| Strategy | Baseline, RAG, Formal, Agentic (multi-select) |
| Model | Configured in Settings (Anthropic / OpenAI / Google / Ollama) |

### Compliance Checker outputs

- Verdict card: ✅ PERMITTED or ❌ DENIED
- Plain-English explanation (LLM2 for formal/agentic; direct LLM for baseline/RAG)
- Cited regulation sections (§164.506, §164.512, etc.)
- Proof tree (formal/agentic only)
- Agentic engine trace (agent A/B/C steps)
- Latency in seconds

### Step-by-step progress (formal / agentic)

The formal and agentic strategies show live status messages while running instead of a static spinner:
```
⠿ Step 1/3 — Sending question to LLM1 (fact extraction)
⠿ Step 1/3 ✓ LLM1 extracted scenario (sender=covered-entity, ...)
⠿ Step 2/3 — Running Soufflé formal engine
⠿ Step 2/3 ✓ Soufflé verdict: PERMITTED  citations: 164.506(c)
⠿ Step 3/3 — Sending verdict to LLM2 (explanation generation)
```

### Batch Eval page inputs / outputs

| Input | Description |
|---|---|
| CSV file upload | Any format (auto-detected: hipaa_qa, goldcoin, privacyci, custom) |
| Strategy | Baseline, RAG, Formal, Agentic |
| Model | From Settings |
| Regulation | From Settings |

Output: downloadable results CSV with `id, question, ground_truth, prediction, match, answer, legal_basis`

---

## 4. CLI — Single Questions & Interactive

```bash
# Interactive mode (default — formal strategy, prompts for questions)
python app/cli.py

# Interactive mode, disable planning rephraser
python app/cli.py --no-plan

# Single question (formal strategy)
python app/cli.py -q "Can a hospital share records with a patient's employer?"

# Single question, specific strategy
python app/cli.py -q "Can a hospital share records?" --strategy baseline
python app/cli.py -q "Can a hospital share records?" --strategy rag
python app/cli.py -q "Can a hospital share records?" --strategy formal
python app/cli.py -q "Can a hospital share records?" --strategy agentic

# Run all four strategies on one question
python app/cli.py -q "Can a hospital share records?" --strategy all

# Override model (provider/model-id format)
python app/cli.py -q "..." --strategy formal   --model anthropic/claude-sonnet-4-6
python app/cli.py -q "..." --strategy baseline --model openai/gpt-4o
python app/cli.py -q "..." --strategy baseline --model ollama/llama3.2:latest
python app/cli.py -q "..." --strategy baseline --model google/gemini-2.0-flash

# Show step-by-step progress for formal/agentic
python app/cli.py -q "..." --strategy formal --progress

# Batch evaluation from CLI
python app/cli.py --benchmark data/hipaa_qa.csv --strategy formal
python app/cli.py --benchmark data/goldcoin.csv --strategy all --output results.csv

# Batch eval with model override
python app/cli.py --benchmark data/hipaa_qa.csv --strategy baseline \
    --model anthropic/claude-sonnet-4-6
```

### Planning phase (default: on)

For first-person or relational questions ("Can I…", "my wife's…"), the CLI automatically rephrases to canonical third-person form before running the strategy:

```
IN:  "Can I access my wife's medical records?"
OUT: "Can a patient access their spouse's medical records held by a hospital?"
```

Disable with `--no-plan`. Batch eval always skips planning.

### CLI inputs summary

| Flag | Default | Description |
|---|---|---|
| `-q / --question` | — | Single question to evaluate |
| `--strategy` | `formal` | `baseline`, `rag`, `formal`, `agentic`, or `all` |
| `--model` | from settings | `provider/model-id` override |
| `--benchmark` | — | Path to CSV for batch evaluation |
| `--output` | auto | Output CSV path for batch eval |
| `--progress` | off | Show per-step feedback |
| `--no-plan` | — | Disable question planning/rephrasing |
| `--verbose` | off | Print raw LLM responses |

### CLI outputs

- **Single question**: verdict + explanation + citations printed to terminal
- **Batch**: CSV written to `--output` or `results/<timestamp>.csv`

---

## 5. Batch Runner (`app/batch_runner.py`)

Evaluates a CSV dataset with one strategy. Called internally by `run_benchmark.py`, but also usable directly.

```bash
# Basic — run formal strategy on HIPAA QA (uses model from settings)
python app/batch_runner.py --input data/hipaa_qa.csv

# Specify strategy
python app/batch_runner.py --input data/hipaa_qa.csv --strategy baseline
python app/batch_runner.py --input data/hipaa_qa.csv --strategy rag
python app/batch_runner.py --input data/hipaa_qa.csv --strategy formal
python app/batch_runner.py --input data/hipaa_qa.csv --strategy agentic
python app/batch_runner.py --input data/hipaa_qa.csv --strategy all

# Prompt-engineering ablation variants
python app/batch_runner.py --input data/hipaa_qa.csv --strategy baseline_fs
python app/batch_runner.py --input data/hipaa_qa.csv --strategy baseline_cot
python app/batch_runner.py --input data/hipaa_qa.csv --strategy baseline_fscot
python app/batch_runner.py --input data/hipaa_qa.csv --strategy rag_fs
python app/batch_runner.py --input data/hipaa_qa.csv --strategy rag_cot
python app/batch_runner.py --input data/hipaa_qa.csv --strategy rag_fscot

# Override model
python app/batch_runner.py --input data/hipaa_qa.csv --model ollama/llama3.2:latest
python app/batch_runner.py --input data/hipaa_qa.csv --model anthropic/claude-sonnet-4-6

# Other regulations
python app/batch_runner.py --input data/gdpr_qa.csv  --strategy baseline --regulation gdpr
python app/batch_runner.py --input data/glba_qa.csv  --strategy formal   --regulation glba
python app/batch_runner.py --input data/ccpa_qa.csv  --strategy rag      --regulation ccpa
python app/batch_runner.py --input data/coppa_qa.csv --strategy agentic  --regulation coppa
python app/batch_runner.py --input data/sox_qa.csv   --strategy baseline --regulation sox

# GoldCoin dataset (107 narrative scenarios)
python app/batch_runner.py --input data/goldcoin.csv --strategy formal

# Limit rows (fast testing)
python app/batch_runner.py --input data/hipaa_qa.csv --limit 5

# Custom output path
python app/batch_runner.py --input data/hipaa_qa.csv --output results/my_run.csv

# Verbose (print LLM answer snippets)
python app/batch_runner.py --input data/hipaa_qa.csv --verbose

# Preview column detection without running
python app/batch_runner.py --input data/hipaa_qa.csv --preview

# Delay between rows (useful for rate-limited APIs)
python app/batch_runner.py --input data/hipaa_qa.csv --delay 2.0
```

### Inputs

| Flag | Default | Description |
|---|---|---|
| `--input` | required | Path to CSV dataset |
| `--strategy` | `formal` | Strategy name (see above) |
| `--model` | from settings | `provider/model-id` |
| `--regulation` | `hipaa` | Active regulation |
| `--output` | auto-named | Results CSV path |
| `--limit` | all rows | Max rows to process |
| `--verbose` | off | Print LLM snippets |
| `--preview` | off | Show column detection only |
| `--delay` | `0.0` | Seconds between rows |

### Auto-detected CSV formats

| Format | Question column | Ground-truth column |
|---|---|---|
| `hipaa_qa.csv` | `question` | `answer` (Yes/No) |
| `goldcoin.csv` | `generate_background` | `generate_HIPAA_type` (Permit/Forbid) |
| `privacyci.csv` | `case_content` | `norm_type` (permit/prohibit) |
| Any other | first column with "question" in name | auto-detected |

### Output columns

| Column | Description |
|---|---|
| `id` | Row identifier |
| `question` | Input question |
| `ground_truth` | Gold label (PERMITTED / DENIED) |
| `prediction` | Model's verdict |
| `match` | Y if correct, N if not |
| `answer` | Full model response |
| `legal_basis` | Cited sections |
| `latency_seconds` | Time per row |
| `strategy` | Strategy used |
| `model` | Model used |

---

## 6. Benchmark Runner (`run_benchmark.py`)

Loops over all combinations of models × strategies × datasets and prints an accuracy table. Used by `run_ablation.sh`.

```bash
# Default: HIPAA datasets, all installed Ollama models, baseline+rag+formal
python run_benchmark.py

# Quick test — 5 rows per dataset
python run_benchmark.py --limit 5

# Specific strategies
python run_benchmark.py --strategies baseline --limit 5
python run_benchmark.py --strategies formal agentic --limit 5
python run_benchmark.py --strategies baseline baseline_fs baseline_cot baseline_fscot \
                         rag rag_fs rag_cot rag_fscot formal agentic

# Specific models
python run_benchmark.py --models llama3.2:latest mistral:latest --limit 5
python run_benchmark.py --models llama3.3:70b-instruct-q4_0 --strategies formal

# One regulation
python run_benchmark.py --regulation gdpr --limit 5
python run_benchmark.py --regulation hipaa

# All 6 regulations
python run_benchmark.py --regulation all --limit 3

# Specific datasets
python run_benchmark.py --datasets goldcoin hipaa_qa
python run_benchmark.py --datasets gdpr_qa ccpa_qa

# Resume after interruption (skip completed CSVs)
python run_benchmark.py --skip-existing

# HuggingFace backend (SLURM cluster)
python run_benchmark.py --backend hf \
    --models meta-llama/Llama-3.1-8B-Instruct \
    --strategies baseline rag --datasets goldcoin

# HF tier shortcut
python run_benchmark.py --backend hf --hf-tier small   # 7-9B models
python run_benchmark.py --backend hf --hf-tier medium  # 13-14B models
python run_benchmark.py --backend hf --hf-tier large   # 32-70B models

# Verbose output
python run_benchmark.py --limit 2 --verbose
```

### Inputs

| Flag | Default | Description |
|---|---|---|
| `--backend` | `ollama` | `ollama` or `hf` (HuggingFace) |
| `--strategies` | `baseline rag formal` | Space-separated list of strategies |
| `--datasets` | HIPAA defaults | Space-separated dataset names |
| `--regulation` | — | Run all datasets for a regulation (`hipaa`, `gdpr`, ..., `all`) |
| `--models` | installed Ollama models | Space-separated model names |
| `--hf-tier` | — | HF shortcut: `small`, `medium`, `large` |
| `--limit` | all | Max rows per dataset |
| `--skip-existing` | off | Skip runs whose output CSV already has data |
| `--verbose` | off | Print LLM answer snippets |
| `--delay` | `0.0` | Seconds between rows (HF rate-limiting) |

### Output

- Results CSVs: `results/<timestamp>/<dataset>__<strategy>__<model>.csv`
- Run log: `results/<timestamp>/run.log`
- Accuracy table printed to terminal and saved to log

---

## 7. Soufflé Engine — Direct

Run the formal Datalog engine standalone, with no Python and no LLM.

```bash
# HIPAA — evaluate all current facts
souffle -D output_hipaa/ datalog_engine/hipaa_top.dl

# GDPR
souffle -D /tmp/gdpr_out/ datalog_engine/gdpr_top.dl

# GLBA
souffle -D /tmp/glba_out/ datalog_engine/glba_top.dl

# CCPA
souffle -D /tmp/ccpa_out/ datalog_engine/ccpa_top.dl

# COPPA
souffle -D /tmp/coppa_out/ datalog_engine/coppa_top.dl

# SOX
souffle -D /tmp/sox_out/ datalog_engine/sox_top.dl

# Interactive proof-tree explorer (HIPAA)
souffle -t explain datalog_engine/hipaa_top.dl

# Multi-threaded
souffle -j 4 -D output_hipaa/ datalog_engine/hipaa_top.dl

# HTML debug report (requires Graphviz)
souffle -r report.html datalog_engine/hipaa_top.dl
```

### Soufflé input (how to add custom facts)

Edit `datalog_engine/hipaa_query_facts.dl` (created fresh per run by `FormalStrategy`) or inline facts directly in a `.dl` file:

```prolog
// Example: hospital shares diagnosis with insurer for payment
disclosure_attempted("hospital_a", "covered-entity",
                     "insurer_a", "health-plan",
                     "patient_a", "adult",
                     "diagnosis", "payment", "msg_001").
```

Then run:
```bash
souffle -D /tmp/out/ datalog_engine/hipaa_top.dl
cat /tmp/out/is_disclosure_allowed.csv
```

### Soufflé output files

| File | Contents |
|---|---|
| `is_disclosure_allowed.csv` | Tuples where disclosure is PERMITTED |
| `is_disclosure_denied.csv` | Tuples where disclosure is DENIED |
| `permitted_by_164_502.csv` | Permitted under §164.502 |
| `permitted_by_164_506.csv` | Permitted under §164.506 |
| `excluded_164_502_b_2.csv` | Excluded by §164.502(b)(2) |
| `minimum_necessary_satisfied.csv` | Minimum necessary satisfied |
| `is_personal_representative.csv` | Personal representative relationships |

---

## 8. Python API — Direct Strategy Use

Use any strategy from Python without the CLI or UI.

```python
import sys
sys.path.insert(0, ".")
sys.path.insert(0, "app")

from connector.settings import get_settings

# Configure model (optional — uses defaults from .compliancegpt_settings.json)
s = get_settings()
s["active_regulation"] = "hipaa"       # hipaa | gdpr | glba | ccpa | coppa | sox
s["llm1_provider"]     = "anthropic"   # anthropic | openai | ollama | google | huggingface
s["llm1_model"]        = "claude-sonnet-4-6"
s["llm2_provider"]     = "anthropic"
s["llm2_model"]        = "claude-sonnet-4-6"
# s.save()  # persist to .compliancegpt_settings.json (optional)
```

### Baseline strategy

```python
from strategies.baseline import BaselineStrategy

result = BaselineStrategy().run("Can a hospital share a patient's diagnosis with their employer?")
print(result.verdict)   # PERMITTED or DENIED
print(result.answer)    # Full explanation
print(result.model)     # Model used
print(result.latency_seconds)
```

### RAG strategy

```python
from strategies.rag import RAGStrategy

strat = RAGStrategy()
strat.build_index()   # loads regulation knowledge base (cached after first call)
result = strat.run("Does HIPAA allow disclosures for public health activities?")
print(result.verdict)
print(result.citations)
print(result.retrieved_docs)  # list of retrieved chunks
```

### Formal strategy (Soufflé)

```python
from strategies.formal import FormalStrategy

# Full pipeline: LLM1 → Soufflé → LLM2
result = FormalStrategy().run("Can a hospital share PHI with another provider for treatment?")
print(result.verdict)            # PERMITTED / DENIED / UNKNOWN / ERROR
print(result.answer)             # LLM2 plain-English explanation
print(result.citations)          # ['164.506(c)(2)', ...]
print(result.explanation_tree)   # Soufflé proof tree
print(result.scenario_json)      # LLM1 extracted scenario
print(result.generated_facts)    # Datalog facts sent to Soufflé
print(result.run_dir)            # Path to artifact directory

# With live progress callback
def show(msg): print(f"  > {msg}")
result = FormalStrategy().run("...", progress_callback=show)

# Skip LLM1 — provide DatalogScenario directly
from connector.hipaa_engine import DatalogScenario
scenario = DatalogScenario(
    sender="hospital_a",    sender_role="covered-entity",
    receiver="insurer_a",   receiver_role="health-plan",
    subject="patient_a",    subject_category="adult",
    attribute="diagnosis",  purpose="payment",
)
result = FormalStrategy().run_with_scenario(scenario, "Original question text")
```

### Agentic strategy

```python
from strategies.agentic import AgenticStrategy

result = AgenticStrategy().run("Is it allowed to use patient data for marketing?")
print(result.verdict)
print(result.answer)
print(result.retry_count)        # Number of self-correction cycles
for trace in result.traces:
    print(trace.agent, trace.output_summary)
```

### RegulationRouter (production path used by the UI)

```python
from regulation_router import RegulationRouter

# Routes to the right strategy+regulation combination automatically
result = RegulationRouter().run("formal", "Can a hospital share PHI for treatment?")
result = RegulationRouter().run("baseline", "Is this GDPR compliant?")  # needs active_regulation=gdpr
```

### LLM client directly

```python
from connector.model_client import ModelClient

client = ModelClient(provider="anthropic", model="claude-sonnet-4-6")
response = client.complete(
    system="You are a HIPAA expert.",
    user="Can a hospital share a diagnosis with the patient's insurer for billing?",
    max_tokens=500,
)
print(response)  # plain text string

# Ollama
client = ModelClient(provider="ollama", model="llama3.2:latest")
response = client.complete(system="...", user="...", max_tokens=300)
```

---

## 9. Evaluation Scripts

All scripts run from the project root.

### Component 1 — Soufflé engine isolation

Tests the Soufflé formal engine in isolation using oracle scenario facts parsed from GoldCoin's `generate_characteristics` field (bypasses LLM1 entirely). Per-row artifact directories contain the `.dl` facts file and all Soufflé output CSVs for **manual verification**.

```bash
# Full run (107 GoldCoin rows, Claude maps characteristics → DatalogScenario)
python eval_component1_souffle.py

# Specify model for characteristics mapping
python eval_component1_souffle.py --model anthropic/claude-sonnet-4-6

# Quick test (first 5 rows)
python eval_component1_souffle.py --limit 5

# Resume an interrupted run
python eval_component1_souffle.py --skip-existing

# Custom output path
python eval_component1_souffle.py --out data/my_c1.csv
```

**Inputs:** `data/goldcoin.csv` (107 rows)
**Outputs:**
- `data/eval_component1.csv` — per-row summary: `row_id, gold_label, verdict, match, citations, scenario_json, generated_facts, explanation_tree, artifact_dir, latency_s, error`
- `data/eval_component1_artifacts/row_<id>/` — per-row artifact directories:
  - `hipaa_query_facts.dl` — generated Datalog facts
  - `output/is_disclosure_allowed.csv` — Soufflé verdicts
  - `output/permitted_by_164_506.csv` — §164.506 results
  - `result.json` — verdict + metadata

---

### Component 2 — LLM2 faithfulness

Reads Component 1 Soufflé outputs, runs LLM2 (Claude) on each to generate explanations, and scores faithfulness.

```bash
python eval_component2_llm2.py

# With rubric scoring
python eval_component2_llm2.py \
    --component1 data/eval_component1.csv \
    --rubric data/explanation_rubric.csv \
    --model anthropic/claude-sonnet-4-6

# Limit / resume
python eval_component2_llm2.py --limit 10 --skip-existing
```

**Inputs:** `data/eval_component1.csv` + `data/goldcoin.csv` (for original questions)
**Outputs:** `data/eval_component2.csv` — `row_id, gold_label, verdict, question, explanation, citations, verdict_preserved, citation_grounded, rubric_total, latency_s, error`

---

### Component 3 — Full end-to-end pipeline

Full pipeline with Claude as both LLM1 and LLM2. Accuracy gap vs Component 1 = LLM1 error attribution.

```bash
python eval_e2e.py

python eval_e2e.py --model anthropic/claude-sonnet-4-6

# Quick test
python eval_e2e.py --limit 5

# Resume
python eval_e2e.py --skip-existing
```

**Inputs:** `data/goldcoin.csv` (107 rows)
**Outputs:** `data/eval_e2e.csv` — `row_id, gold_label, verdict, match, answer, citations, scenario_json, latency_s, error`

---

### LLM1 field-level accuracy

Measures how well LLM1 extracts DatalogScenario fields vs a gold standard.

```bash
# Small hand-annotated gold standard (7 rows)
python evaluate_llm1.py --gold data/llm1_gold_standard.csv

# Full GoldCoin benchmark (107 rows, generate_characteristics as gold)
python evaluate_llm1.py --goldcoin data/goldcoin.csv

# Specify model
python evaluate_llm1.py --goldcoin data/goldcoin.csv \
    --model anthropic/claude-sonnet-4-6

# Custom output
python evaluate_llm1.py --goldcoin data/goldcoin.csv \
    --out evaluate_llm1_goldcoin_results.csv
```

**Inputs:** `data/llm1_gold_standard.csv` or `data/goldcoin.csv`
**Outputs:** `evaluate_llm1_results.csv` — per-row field comparisons + aggregate accuracy table printed to stdout

---

### LLM2 faithfulness evaluation

Evaluates LLM2 explanation faithfulness across results CSVs. Three checks: verdict preservation, citation grounding, optional LLM-as-judge.

```bash
# Run on all results CSVs in a directory
python evaluate_llm2.py --results results/20260504_200149/

# With rubric scoring
python evaluate_llm2.py \
    --results results/20260504_200149/ \
    --rubric  data/explanation_rubric.csv

# With LLM-as-judge (rates faithfulness 1–5)
python evaluate_llm2.py \
    --results results/20260504_200149/ \
    --judge   anthropic/claude-sonnet-4-6

# All three checks together
python evaluate_llm2.py \
    --results results/20260504_200149/ \
    --rubric  data/explanation_rubric.csv \
    --judge   anthropic/claude-sonnet-4-6 \
    --out     evaluate_llm2_results.csv
```

**Inputs:** Any results directory with `*formal*.csv` files
**Outputs:** `evaluate_llm2_results.csv` — per-row scores + aggregate faithfulness table

---

### Analyze results (figures + summary tables)

```bash
# Auto-find latest results directory
python analyze_results.py

# Specific directory
python analyze_results.py --results results/20260504_200149/

# Custom output directory
python analyze_results.py --out analysis_out/

# CSV only (no plots)
python analyze_results.py --no-plots
```

**Outputs:** `analysis.csv`, `missing.csv`, `figures/*.png` (8 figures: completion heatmaps, accuracy heatmaps, strategy comparison, ablation study, coverage pie, error rates, latency)

---

## 10. Datasets

| Dataset | File | Rows | Regulation | Format | Notes |
|---|---|---|---|---|---|
| GoldCoin | `data/goldcoin.csv` | 107 | HIPAA | Narrative | Real court cases from Harvard CAP; Permit/Forbid labels |
| HIPAA QA | `data/hipaa_qa.csv` | 59 | HIPAA | Q&A | Hand-crafted; Yes/No labels |
| GDPR QA | `data/gdpr_qa.csv` | varies | GDPR | Q&A | |
| GLBA QA | `data/glba_qa.csv` | varies | GLBA | Q&A | |
| CCPA QA | `data/ccpa_qa.csv` | varies | CCPA | Q&A | |
| COPPA QA | `data/coppa_qa.csv` | varies | COPPA | Q&A | |
| SOX QA | `data/sox_qa.csv` | varies | SOX | Q&A | |
| LLM1 gold std | `data/llm1_gold_standard.csv` | 7 | HIPAA | Annotated | For `evaluate_llm1.py --gold` |
| Explanation rubric | `data/explanation_rubric.csv` | 20 | HIPAA | Annotated | For `evaluate_llm2.py --rubric` |

Ground-truth normalization: `Permit`/`permit`/`Yes`/`yes`/`allowed` → `PERMITTED`; `Forbid`/`prohibit`/`No`/`denied` → `DENIED`.

---

## 11. Strategies

| Strategy key | Description |
|---|---|
| `baseline` | Zero-shot LLM: system prompt + question, one LLM call |
| `baseline_fs` | Baseline + 3 few-shot examples |
| `baseline_cot` | Baseline + chain-of-thought instruction |
| `baseline_fscot` | Baseline + few-shot + chain-of-thought |
| `rag` | RAG: BM25 retrieves top-k chunks from regulation text, injected into prompt |
| `rag_fs` | RAG + few-shot |
| `rag_cot` | RAG + chain-of-thought |
| `rag_fscot` | RAG + few-shot + chain-of-thought |
| `formal` | LLM1 extracts DatalogScenario JSON → Soufflé engine → LLM2 plain-English explanation |
| `agentic` | Multi-agent: Agent A (entities) → Agent B (sections) → Agent C (validation) → Soufflé → Agent E (explanation) |

---

## 12. Models

### Ollama (local, no API key required)

| Model tag | Size | Notes |
|---|---|---|
| `llama3.2:latest` | ~2 GB | Meta small, fast smoke-check |
| `phi4:latest` | ~9 GB | Microsoft Phi-4, strong small model |
| `mistral:latest` | ~4 GB | Classic open-source baseline |
| `gemma:7b` | ~5 GB | Google Gemma |
| `gpt-oss:latest` | ~13 GB | GPT-family open source |
| `qwen3:14b` | ~9 GB | Alibaba medium, strong reasoning |
| `qwen2.5-coder:32b-instruct` | ~19 GB | Strong general instruction model |
| `deepseek-r1:70b` | ~42 GB | Reasoning / CoT specialist |
| `llama3.1:70b` | ~42 GB | Meta large, general |
| `llama3.3:70b` | ~42 GB | Meta large, latest |
| `llama3.3:70b-instruct-q4_0` | ~39 GB | Meta large, instruction-tuned ★ primary |
| `qwen2.5:72b` | ~47 GB | Alibaba large |
| `command-r-plus:latest` | ~59 GB | Cohere, purpose-built for RAG |

Pull a model: `ollama pull <model-tag>`

### Anthropic (API key required)

| Model ID | Notes |
|---|---|
| `claude-sonnet-4-6` | Default — balanced capability + speed |
| `claude-opus-4-6` | Most capable |
| `claude-haiku-4-5-20251001` | Fast, low cost |

### OpenAI, Google, HuggingFace

Configure in Settings or pass as `--model provider/model-id`.

---

## 13. Regulations

| Key | Full name | Strategy support |
|---|---|---|
| `hipaa` | HIPAA Privacy Rule (45 CFR §164) | All 10 strategies fully formalized |
| `gdpr` | GDPR (EU 2016/679) | All 10 strategies; formal via NonHIPAAExtractor |
| `glba` | GLBA (Gramm-Leach-Bliley Act) | All 10 strategies |
| `ccpa` | CCPA (California Consumer Privacy Act) | All 10 strategies |
| `coppa` | COPPA (16 CFR §312) | All 10 strategies |
| `sox` | SOX (Sarbanes-Oxley Act) | All 10 strategies |

All 6 × 10 = 60 regulation × strategy combinations are confirmed working with 0 errors.

---

## 14. Output Files

### Benchmark results

```
results/
└── 20260504_200149/
    ├── run.log                                          ← accuracy table + run metadata
    ├── goldcoin__baseline__llama3.2_latest.csv
    ├── goldcoin__rag__llama3.2_latest.csv
    ├── goldcoin__formal__llama3.3_70b-instruct-q4_0.csv
    ├── hipaa_qa__baseline__mistral_latest.csv
    └── ...
```

### Component eval outputs

```
data/
├── eval_component1.csv                   ← Component 1 summary
├── eval_component1_artifacts/
│   ├── row_1/
│   │   ├── hipaa_query_facts.dl          ← Generated Datalog facts (manual verification)
│   │   ├── output/
│   │   │   ├── is_disclosure_allowed.csv
│   │   │   ├── permitted_by_164_502.csv
│   │   │   └── permitted_by_164_506.csv
│   │   └── result.json
│   ├── row_2/
│   └── ...
├── eval_component2.csv                   ← LLM2 faithfulness scores
└── eval_e2e.csv                          ← End-to-end accuracy
```

### Formal strategy run artifacts

```
runs/
└── run_20260504_143022_abc123/
    ├── hipaa_query_facts.dl     ← Facts sent to Soufflé
    ├── hipaa_query_main.dl      ← Main include file
    ├── output/
    │   ├── is_disclosure_allowed.csv
    │   ├── is_disclosure_denied.csv
    │   └── ...
    └── result.json              ← Verdict + metadata
```

---

## 15. Settings Reference

Settings file: `.compliancegpt_settings.json` (auto-created on first run).

| Key | Default | Description |
|---|---|---|
| `active_regulation` | `hipaa` | Current regulation: `hipaa`, `gdpr`, `glba`, `ccpa`, `coppa`, `sox` |
| `llm1_provider` | `anthropic` | LLM1 provider: `anthropic`, `openai`, `ollama`, `google`, `huggingface` |
| `llm1_model` | `claude-sonnet-4-6` | LLM1 model ID |
| `llm2_provider` | `anthropic` | LLM2 (explainer) provider |
| `llm2_model` | `claude-sonnet-4-6` | LLM2 model ID |
| `ollama_base_url` | `http://localhost:11434` | Ollama server URL |
| `souffle_binary` | `""` (auto-detect) | Path to Soufflé binary |
| `souffle_timeout` | `30` | Max seconds for Soufflé |
| `rag_k` | `5` | Documents to retrieve |
| `rag_alpha` | `0.5` | RAG hybrid weight (0=BM25, 1=semantic) |

**Change via Python (in-memory, no file write):**
```python
from connector.settings import get_settings
s = get_settings()
s["active_regulation"] = "gdpr"
s["llm1_model"] = "claude-sonnet-4-6"
# s.save()  # write to .compliancegpt_settings.json
```

**Change via Streamlit:** Settings → Save

**Change via CLI flags:** `--model`, `--regulation` flags on `batch_runner.py` / `run_benchmark.py`

---

## 16. Repository Structure

```
COMPLIANCEGPT/
│
├── run_ablation.sh            ← ONE command: Ollama benchmark + all component evals
├── run_benchmark.py           ← Meta-runner: models × strategies × datasets
├── setup.sh                   ← One-command setup + dependency check
├── analyze_results.py         ← Figures + accuracy tables from results/
│
├── eval_component1_souffle.py ← Component 1: Soufflé isolation (oracle facts)
├── eval_component2_llm2.py    ← Component 2: LLM2 explanation dataset
├── eval_e2e.py                ← Component 3: Full end-to-end (Claude)
├── evaluate_llm1.py           ← LLM1 field-level accuracy
├── evaluate_llm2.py           ← LLM2 faithfulness evaluation
│
├── app/
│   ├── streamlit_app.py       ← Streamlit web UI (single file, 4 pages)
│   ├── cli.py                 ← Interactive + single-question + batch CLI
│   ├── batch_runner.py        ← Single-run worker (one dataset, one strategy)
│   ├── regulation_router.py   ← Routes question to correct strategy + regulation
│   └── strategies/
│       ├── baseline.py        ← Zero-shot LLM
│       ├── rag.py             ← Hybrid BM25 + semantic retrieval
│       ├── formal.py          ← LLM1 → Soufflé → LLM2
│       └── agentic.py         ← Multi-agent pipeline
│
├── connector/
│   ├── model_client.py        ← Unified LLM client (Anthropic, OpenAI, Ollama, Google, HF)
│   ├── settings.py            ← Persistent settings singleton
│   ├── dataset_loader.py      ← Smart CSV loader (3 benchmark formats)
│   ├── llm1_extractor.py      ← NL question → DatalogScenario JSON
│   ├── llm2_explainer.py      ← EngineResult → plain-English explanation
│   ├── hipaa_engine.py        ← Soufflé runner + DatalogScenario / EngineResult
│   ├── planner.py             ← Question planner (first-person → canonical form)
│   └── non_hipaa_extractor.py ← Short-prompt extractor for non-HIPAA regulations
│
├── datalog_engine/
│   ├── AGENT_PROMPT.md        ← LLM1 system prompt (~12 500 tokens)
│   ├── hipaa_top.dl           ← Soufflé HIPAA entry point
│   ├── hipaa_164_502.dl       ← §164.502 rules
│   ├── hipaa_164_506.dl       ← §164.506 rules
│   ├── hipaa_164_512.dl       ← §164.512 rules
│   ├── gdpr_top.dl            ← GDPR Soufflé rules
│   ├── glba_top.dl            ← GLBA Soufflé rules
│   ├── ccpa_top.dl            ← CCPA Soufflé rules
│   ├── coppa_top.dl           ← COPPA Soufflé rules
│   └── sox_top.dl             ← SOX Soufflé rules
│
├── data/
│   ├── goldcoin.csv           ← 107-row GoldCoin HIPAA benchmark
│   ├── hipaa_qa.csv           ← 59-row hand-crafted HIPAA Q&A
│   ├── gdpr_qa.csv / gdpr_rag_db.csv
│   ├── glba_qa.csv / glba_rag_db.xml
│   ├── ccpa_qa.csv / ccpa_rag_db.csv
│   ├── coppa_qa.csv / coppa_rag_db.xml
│   ├── sox_qa.csv
│   ├── llm1_gold_standard.csv ← 7-row LLM1 eval gold standard
│   └── explanation_rubric.csv ← 20-row LLM2 rubric dataset
│
└── results/                   ← Benchmark output CSVs (git-ignored)
```

---

## 17. Troubleshooting

**"Cannot reach Ollama"**
```
Run `ollama serve` in a separate terminal, then retry.
```

**"Model not installed"**
```bash
ollama pull <model-tag>    # e.g. ollama pull llama3.2:latest
```

**"Soufflé binary not found" (formal/agentic)**
```bash
brew install souffle-lang/souffle/souffle   # macOS
sudo apt-get install souffle               # Ubuntu
souffle --version                          # verify
```

**"Verdict is UNKNOWN" (formal)**
LLM1 extracted an invalid constant. Add `--verbose` to see the extracted JSON.
Small models (<27B) frequently fail on the formal strategy — this is expected and logged.

**"RAG always returns §164.502"**
BM25 is flooding on long GoldCoin narratives. The runner automatically uses the last 3 sentences for retrieval. If you're calling RAGStrategy directly, use `strategy.run(question[-500:])` or set a shorter query.

**"ModuleNotFoundError: rank_bm25"**
```bash
pip install rank-bm25
```

**"Component 1/2/3 scripts skipped or failing"**
Component evals run via Ollama by default — no API key needed. Ensure Ollama is running (`ollama serve`) and the component model is pulled (`ollama pull llama3.3:70b-instruct-q4_0`).

**Resuming after a crash**
Any script with `--skip-existing` will skip rows/files that already have output. Safe to re-run.

**Settings file corrupted**
Delete `.compliancegpt_settings.json` — it will be recreated with defaults on the next run.
