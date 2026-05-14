# HIPAA Compliance Pipeline — Python Connector

This connects your natural language interface to the Souffle HIPAA 
compliance engine via a three-step pipeline.

```
User Question
    ↓
LLM1 (llm1_extractor.py)   — extracts structured scenario from text
    ↓
Souffle Engine (hipaa_engine.py)  — formal HIPAA compliance check
    ↓
LLM2 (llm2_explainer.py)   — turns formal result into plain English
    ↓
Human-readable answer
```

---

## Setup

### 1. Install Python dependencies (in a virtual environment)

```bash
cd ComplianceGPT/datalog_engine   # your project root
python3 -m venv venv
source venv/bin/activate           # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy the four Python files into your project directory:
```
hipaa_engine.py
llm1_extractor.py
llm2_explainer.py
hipaa_pipeline.py
requirements.txt
```

### 2. Install Souffle (if not already installed)

```bash
# macOS
brew install souffle-lang/souffle/souffle

# Ubuntu/Debian
sudo apt-get install souffle

# Or build from source: https://souffle-lang.github.io/install
```

Verify: `souffle --version`

### 3. Set your Anthropic API key

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Usage

### Single question (interactive)

```bash
python hipaa_pipeline.py --souffle-dir /path/to/datalog_engine

# You'll see:
# Your question: Can I see my lab results before my doctor reviews them?
```

### Single question (command line)

```bash
python hipaa_pipeline.py \
    --souffle-dir /path/to/datalog_engine \
    --question "Can I see my lab results before my doctor reviews them?"
```

### Batch mode — test against your benchmark CSV

```bash
python hipaa_pipeline.py \
    --souffle-dir /path/to/datalog_engine \
    --benchmark /path/to/your_benchmark.csv \
    --output results.csv
```

Your benchmark CSV must have at minimum:
- `question` column — the natural language question
- `answer` column — `Yes` (allowed) or `No` (denied)

Optional columns used if present: `id`, `topic`, `complexity`, `regulation`, `explanation`

### Verbose mode (see extracted JSON)

```bash
python hipaa_pipeline.py \
    --souffle-dir /path/to/datalog_engine \
    --question "My question here" \
    --verbose
```

---

## File Overview

| File | What it does |
|------|-------------|
| `hipaa_engine.py` | Core connector: converts scenario → Datalog facts → runs Souffle → parses CSV output |
| `llm1_extractor.py` | LLM1: natural language → structured `DatalogScenario` object |
| `llm2_explainer.py` | LLM2: `EngineResult` → human-readable plain English answer |
| `hipaa_pipeline.py` | End-to-end runner (single question, interactive, or batch CSV) |

---

## How the Engine Works (for your understanding)

Souffle is a Datalog engine — think of it as a very fast logic reasoner.
It is NOT Prolog (which is general-purpose logic programming).
Datalog is more restricted: no function symbols, terminates always, 
very efficient for rule-based reasoning over facts.

Your `.dl` files contain:
- **Facts**: specific true statements about a scenario (who, what, to whom, why)
- **Rules**: HIPAA regulations expressed as logical implications
- **Queries**: what to derive (is this disclosure allowed?)

Python's job is just:
1. Write the facts to a `.dl` file
2. Run `souffle -D output/ main.dl` as a subprocess  
3. Read the output CSV files

That's it. No special Souffle Python library needed.

---

## Troubleshooting

**"Souffle binary not found"**  
→ Install souffle and make sure it's on your PATH, or pass `--souffle-binary /full/path/to/souffle`

**"Souffle error: [compilation error]"**  
→ The generated facts file has a syntax issue. Run with `--verbose` to see the extracted JSON, 
  then check the generated facts by adding a `print(facts_text)` in `hipaa_engine.py`.

**"UNKNOWN: Disclosure was not registered as attempted"**  
→ The facts file was generated but `disclosure_attempted` wasn't matched. 
  Usually means a string constant mismatch. Check that roles/attributes/purposes 
  are in the valid lists in `llm1_extractor.py`.

**LLM1 extracts wrong roles/purposes**  
→ Improve the system prompt examples in `LLM1_SYSTEM_PROMPT` in `llm1_extractor.py`.
  Add few-shot examples for the specific question types you're seeing.
