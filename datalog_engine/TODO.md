## ComplianceGPT — Open Issues and Design Notes

---

### ✅ DONE: Step-by-step progress feedback (CLI + UI)

**Implemented:** `progress_callback` parameter added to `FormalStrategy.run()` and
`AgenticStrategy.run()`. The CLI (`app/cli.py`) passes a printer callback for
formal/agentic strategies so users see each stage:

```
  [formal] Step 1/3 — Sending question to LLM1 (fact extraction)
  [formal] Step 1/3 ✓ LLM1 extracted scenario (sender=hospital, receiver=insurer, ...)
  [formal] Step 2/3 — Running Soufflé formal engine
  [formal] Step 2/3 ✓ Soufflé verdict: PERMITTED  citations: 164.506(c)
  [formal] Step 3/3 — Sending verdict to LLM2 (explanation generation)
  [formal] Step 3/3 ✓ Done — verdict: PERMITTED  (8.4s)
```

For Streamlit: wire `progress_callback` into `st.empty()` status updates in the
formal/agentic strategy cards (next UI iteration).

---

### ✅ DONE: Planning phase for first-person / relational questions

**Implemented:** `connector/planner.py` — `QuestionPlanner` class.
Detects first-person pronouns ("I", "my", "can I") and relational terms
("wife", "husband", "child", "parent") and calls the LLM to rephrase into
canonical third-person form before passing to LLM1.

**Example (advisor's test case):**
```
IN:  "Can I access my wife's medical records?"
OUT: "Can a patient access their spouse's medical records held by a hospital?"
```

Active by default in `app/cli.py` interactive mode. Disable with `--no-plan`.
Batch eval intentionally skips planning (GoldCoin/hipaa_qa questions are canonical).

---

### ✅ DONE: One-command end-to-end setup

**Implemented:** `setup.sh`
```bash
bash setup.sh            # full setup (installs deps + Soufflé)
bash setup.sh --check    # diagnose only, no changes
bash setup.sh --pull-models  # also pull all 9 Ollama models
```

Checks Python, installs pip deps, installs Soufflé if missing, verifies Ollama,
creates `.compliancegpt_settings.json` defaults. No manual environment variable
or venv activation needed.

---

### ✅ DONE: End-to-end analysis and visualization

**Implemented:** `analyze_results.py` updated for:
- Ollama model names (all 9 advisor models)
- All 10 strategies (8 prompt ablation + formal + agentic)
- 8 figures: completion heatmaps, accuracy heatmaps (core 4), strategy comparison
  Δ-accuracy chart, ablation study (Fig 8), coverage pie, error rates, latency

```bash
python analyze_results.py                    # auto-finds results/
python analyze_results.py --out analysis_out # custom output
python analyze_results.py --no-plots         # CSV only
```

Output: `analysis.csv`, `missing.csv`, `figures/*.png`

---

### ✅ DONE: LLM1 evaluation (NL → Datalog fact extraction quality)

**Implemented:** `evaluate_llm1.py` at project root.

Gold standard: `data/llm1_gold_standard.csv` — 7 annotated rows covering
treatment, BA payment, law enforcement, patient access, marketing (denied),
employment (denied), and public health scenarios. Extend by adding rows to the CSV.

```bash
python evaluate_llm1.py --gold data/llm1_gold_standard.csv
python evaluate_llm1.py --gold data/llm1_gold_standard.csv \
    --model ollama/llama3.3:70b-instruct-q4_0
```

Reports per-field match rates: sender_role / receiver_role / attribute / purpose /
same_org / is_business_associate / is_guardian_of_subject /
obtained_authorization_164_508. Writes `evaluate_llm1_results.csv`.

---

### ✅ DONE: LLM2 evaluation (explanation faithfulness)

**Implemented:** `evaluate_llm2.py` at project root.

Three automatic checks per formal-strategy result row:
1. **Verdict preservation** — explanation text contains PERMITTED/DENIED
2. **Citation grounding** — LLM2 citations ⊆ engine citations
3. **LLM-as-judge** (optional) — capable model rates faithfulness 1–5

```bash
python evaluate_llm2.py --results results/20260504_200149/
python evaluate_llm2.py --results results/20260504_200149/ \
    --judge anthropic/claude-sonnet-4-6
python evaluate_llm2.py --results results/20260504_200149/ \
    --rubric data/explanation_rubric.csv
```

Writes `evaluate_llm2_results.csv` with per-row scores + printed aggregate table.

---

### ✅ DONE: Explanation evaluation dataset

**Implemented:** `data/explanation_rubric.csv` — 20 annotated HIPAA scenarios.

Covers: treatment disclosure, BA payment ops, court-order LE, patient access,
marketing (denied), employment (denied), public health, IRB research waiver,
psychotherapy notes, coroner, de-identified data, Secretary oversight, and more.

5-dimension rubric per answer (scored in `evaluate_llm2.py --rubric`):
1. Correct verdict stated (0/1)
2. Correct section cited (0/1)
3. Correct party roles identified (0/1)
4. Correct PHI category mentioned (0/1)
5. No contradiction with engine output (0/1)

---

### ✅ DONE: Streamlit UI detailed step feedback

**Implemented:** `app/streamlit_app.py` + `app/regulation_router.py`.

For formal/agentic strategies the static spinner is replaced with an
`st.empty()` placeholder that receives live `progress_callback` messages:

```
⠿ Step 1/3 — Sending question to LLM1 (fact extraction)
⠿ Step 1/3 ✓ LLM1 extracted scenario (sender=covered-entity, ...)
⠿ Step 2/3 — Running Soufflé formal engine
⠿ Step 2/3 ✓ Soufflé verdict: PERMITTED  citations: 164.506(c)
⠿ Step 3/3 — Sending verdict to LLM2 (explanation generation)
```

`RegulationRouter.run()` now accepts `progress_callback=None` and passes it
through to `FormalStrategy.run()` and `AgenticStrategy.run()`. Other strategies
(baseline, RAG) still use the original `st.spinner`.

---

### ✅ DONE: All 10 strategies run on all 9 models

`run_ablation.sh` now runs all 9 models × 10 strategies × 2 datasets.
Small models (<27B) will produce logged errors on formal/agentic — this is
intentional and provides empirical evidence of the minimum capability threshold
for the paper.

---

### 🔬 PENDING: Model-swap ablation experiments (Component 3)

**Idea:** Run `eval_e2e.py` with different models for LLM1 (extraction) and LLM2
(explanation) independently. This answers: *"Does a stronger LLM1 or LLM2 matter more
for end-to-end accuracy?"*

**Why this is interesting for the paper:**
- Component 1 (oracle Soufflé) sets the theoretical ceiling — no LLM1 noise.
- Component 3 (e2e, same model for both) shows baseline performance.
- Model-swap ablation reveals which stage is the bottleneck: if swapping in a
  stronger LLM2 barely changes accuracy but a stronger LLM1 does, extraction quality
  is the limiting factor and vice versa.

**Experiment matrix (already coded in `run_ablation.sh` under `SWAP_ABLATION=1`):**

| Tag | LLM1 (extraction) | LLM2 (explanation) | Hypothesis |
|---|---|---|---|
| `claude-claude` | claude-sonnet-4-6 | claude-sonnet-4-6 | Strong-strong baseline |
| `llama-llama` | llama3.2:latest | llama3.2:latest | Weak-weak baseline |
| `mistral-mistral` | mistral:latest | mistral:latest | Mid-mid baseline |
| `qwen-qwen` | qwen3:14b | qwen3:14b | Mid-mid (reasoning) |
| `claude-llama` | claude-sonnet-4-6 | llama3.2:latest | Strong extraction + weak explanation |
| `llama-claude` | llama3.2:latest | claude-sonnet-4-6 | Weak extraction + strong explanation |

**To run:**
```bash
# Run all model-swap experiments (Ollama must be running for local models)
SWAP_ABLATION=1 bash run_ablation.sh

# Or run a single pair manually
python3 eval_e2e.py \
    --llm1 ollama/llama3.2:latest \
    --llm2 anthropic/claude-sonnet-4-6 \
    --out  data/eval_e2e_llama-claude.csv
```

**Output:** `data/eval_e2e_<tag>.csv` per experiment — compare accuracy columns
side by side to attribute which stage drives overall pipeline performance.

**Additional idea:** also run `eval_component1_souffle.py` and `eval_component2_llm2.py`
with local models to see how the mapping step and faithfulness degrade with smaller models.

---
