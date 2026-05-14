"""
app/pages/0_Methodology.py
─────────────────────────────────────────────────────────────────────────────
Methodology page — explains the four compliance verification strategies,
design rationale, and comparative analysis.
"""

import sys
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(
    page_title="Methodology — ComplianceGPT",
    page_icon="📖",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:ital,wght@0,300;0,400;0,600;1,400&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background: #ffffff !important; }
[data-testid="stSidebar"] { background: #f8f9fa !important; border-right: 1px solid #dee2e6; }
[data-testid="stSidebar"] * { color: #212529 !important; }
p, li, span { color: #212529; }
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li { color: #212529; }
h1 { font-family: 'IBM Plex Mono', monospace; color: #1a1a2e; font-size: 1.6rem; border-bottom: 2px solid #dee2e6; padding-bottom: 10px; }
h2 { color: #1a1a2e; font-size: 1.25rem; margin-top: 32px; }
h3 { color: #495057; font-size: 1rem; }
hr { border-color: #dee2e6 !important; }
code { background: #f1f3f5 !important; color: #212529 !important;
       border: 1px solid #dee2e6; border-radius: 3px; padding: 1px 5px;
       font-family: 'IBM Plex Mono', monospace; font-size: 0.82rem; }
pre { background: #f1f3f5 !important; border: 1px solid #dee2e6 !important;
      border-radius: 6px !important; padding: 14px !important; }

/* Strategy cards */
.strategy-card {
    border: 1.5px solid #dee2e6;
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 16px;
    background: #fff;
}
.strategy-card.s1 { border-top: 4px solid #6c757d; }
.strategy-card.s2 { border-top: 4px solid #0d6efd; }
.strategy-card.s3 { border-top: 4px solid #198754; }
.strategy-card.s4 { border-top: 4px solid #6f42c1; }

.strat-num { font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem;
             font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px; }
.s1 .strat-num { color: #6c757d; }
.s2 .strat-num { color: #0d6efd; }
.s3 .strat-num { color: #198754; }
.s4 .strat-num { color: #6f42c1; }

.strat-title { font-size: 1.2rem; font-weight: 700; color: #1a1a2e;
               font-family: 'IBM Plex Sans', sans-serif; margin: 6px 0 12px 0; }

/* Comparison table */
.cmp { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.cmp th { background: #f1f3f5; border: 1px solid #dee2e6; padding: 9px 12px;
          font-family: 'IBM Plex Mono', monospace; font-size: 0.75rem;
          font-weight: 600; color: #495057; text-align: left; }
.cmp td { border: 1px solid #dee2e6; padding: 8px 12px; vertical-align: top; color: #212529; }
.cmp tr:hover td { background: #f8f9fa; }
.check { color: #198754; font-weight: 700; }
.cross { color: #dc3545; font-weight: 700; }
.partial { color: #fd7e14; font-weight: 700; }

/* Pipeline diagram */
.pipe { display: flex; align-items: center; gap: 8px; margin: 12px 0;
        flex-wrap: wrap; font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; }
.pipe-box { background: #f1f3f5; border: 1px solid #dee2e6; border-radius: 6px;
            padding: 6px 12px; color: #212529; white-space: nowrap; }
.pipe-box.highlight { background: #e7f1ff; border-color: #b6d4fe; color: #0a58ca; }
.pipe-box.green { background: #d1e7dd; border-color: #a3cfbb; color: #0a3622; }
.pipe-box.purple { background: #e8d5ff; border-color: #c8a8ff; color: #3a0764; }
.pipe-arr { color: #adb5bd; font-size: 1rem; }

/* Callout boxes */
.callout { border-radius: 6px; padding: 12px 16px; margin: 12px 0; font-size: 0.88rem; }
.callout.pro  { background: #d1e7dd; border-left: 4px solid #198754; color: #0a3622; }
.callout.con  { background: #f8d7da; border-left: 4px solid #dc3545; color: #58151c; }
.callout.note { background: #fff3cd; border-left: 4px solid #ffc107; color: #664d03; }
.callout.key  { background: #e7f1ff; border-left: 4px solid #0d6efd; color: #052c65; }
</style>
""", unsafe_allow_html=True)


st.markdown("# 📖 Methodology")
st.markdown(
    "ComplianceGPT evaluates regulatory compliance questions across **six regulations** "
    "(HIPAA, GDPR, GLBA, CCPA, COPPA, SOX) using four distinct strategies, each with "
    "different tradeoffs between formal guarantees, flexibility, cost, and explainability. "
    "This page explains what each strategy does, why it was designed that way, and how they compare."
)

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# System Overview
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## System Architecture Overview")

st.markdown("""
Every strategy follows the same high-level pipeline, but with different components
filling each stage:
""")

st.markdown("""
<div class="pipe">
  <div class="pipe-box">User question<br><small>(natural language)</small></div>
  <div class="pipe-arr">→</div>
  <div class="pipe-box highlight">Scenario Extraction<br><small>LLM1 or agents</small></div>
  <div class="pipe-arr">→</div>
  <div class="pipe-box highlight">Compliance Check<br><small>Formal engine or LLM</small></div>
  <div class="pipe-arr">→</div>
  <div class="pipe-box green">Plain English Answer<br><small>LLM2 or direct</small></div>
  <div class="pipe-arr">→</div>
  <div class="pipe-box">User</div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
The key design tension is between **formal correctness** (which requires structured 
symbolic reasoning) and **natural language flexibility** (which requires LLMs). 
We address this by using LLMs as a *translation layer* into and out of a formal engine, 
rather than asking LLMs to reason about law directly.
""")

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 1: Baseline
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## Strategy 1 — Baseline LLM")

col1, col2 = st.columns([3, 2])

with col1:
    st.markdown("""
    **What it does:**
    Sends the user's question directly to a language model with a regulation-aware
    system prompt. No retrieval, no formal engine. Pure language model response.

    **How it works:**
    """)

    st.markdown("""
    <div class="pipe">
      <div class="pipe-box">User question</div>
      <div class="pipe-arr">→</div>
      <div class="pipe-box highlight">LLM + regulation system prompt</div>
      <div class="pipe-arr">→</div>
      <div class="pipe-box green">Answer</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    The system prompt instructs the model to:
    - Structure its response with a clear verdict (PERMITTED / NOT PERMITTED)
    - Cite specific regulatory sections (e.g. §164.502 for HIPAA, Art.6 for GDPR)
    - List conditions and exceptions
    
    **Why we include it:**  
    The Baseline serves as the *lower bound* comparison. If a sophisticated strategy 
    (RAG, Formal) can't outperform a plain LLM call, the added complexity isn't 
    justified. It also handles edge cases and novel questions gracefully because 
    language models can reason flexibly about unusual scenarios that the formal 
    engine may not have rules for.
    
    **Known limitations:**  
    LLMs have no guarantees of consistency — the same question asked twice may produce 
    different verdicts. They can hallucinate citations, misremember section numbers, 
    and are vulnerable to adversarial phrasings. Crucially, they reason from training 
    data, not from the regulatory text itself.
    """)

with col2:
    st.markdown("""
    <div class="callout pro">
    ✓ Handles any question, including edge cases outside the formalized rules<br>
    ✓ Fast (single API call)<br>
    ✓ Good with nuance and context<br>
    ✓ No setup required
    </div>
    <div class="callout con">
    ✗ No formal guarantees — can be wrong confidently<br>
    ✗ Non-deterministic across runs<br>
    ✗ May hallucinate citations<br>
    ✗ No audit trail of legal reasoning
    </div>
    <div class="callout note">
    ⚠ Use as a comparison baseline, or for quick answers on questions outside 
    the formal engine's coverage
    </div>
    """, unsafe_allow_html=True)

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 2: RAG
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## Strategy 2 — Retrieval-Augmented Generation (RAG)")

col1, col2 = st.columns([3, 2])

with col1:
    st.markdown("""
    **What it does:**  
    Retrieves the most relevant sections from the actual regulatory text (45 CFR Part 164) 
    and provides them as context to the LLM. The LLM then reasons only over that 
    retrieved text, not its training data.

    **How it works (Algorithm 2):**
    """)

    st.markdown("""
    <div class="pipe">
      <div class="pipe-box">User question</div>
      <div class="pipe-arr">→</div>
      <div class="pipe-box highlight">Hybrid retrieval<br><small>BM25 + Semantic</small></div>
      <div class="pipe-arr">→</div>
      <div class="pipe-box highlight">Top-k CFR sections</div>
      <div class="pipe-arr">→</div>
      <div class="pipe-box highlight">LLM (context-grounded)</div>
      <div class="pipe-arr">→</div>
      <div class="pipe-box green">Answer</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    **Retrieval is hybrid:** we combine two scoring signals:
    
    - **BM25 (lexical):** keyword overlap between query and document chunks. 
      Excellent for exact section references ("§164.508", "marketing authorization").
    - **Semantic (dense):** cosine similarity between query and document embeddings 
      (using `all-MiniLM-L6-v2`). Captures meaning even when exact terms differ.
    
    The hybrid score is: `score = α · semantic + (1-α) · BM25`, with α=0.5 by default 
    (configurable in Settings). Top-k chunks (default k=5) are injected into the prompt.
    
    **Why this matters for legal text:**  
    Legal language is highly specific. "Psychotherapy notes" has a precise legal 
    definition; a pure semantic search might retrieve sections about general medical 
    records instead. BM25 catches exact statutory terms; semantic search catches 
    paraphrased queries. Together they outperform either alone on legal retrieval.
    
    **Knowledge base — regulation-aware routing:**
    Each regulation has its own knowledge base. The active regulation (set in Settings)
    determines which database is loaded:
    - **HIPAA:** eCFR Title 45 parsed into per-section `.txt` files (`data/ecfr_parsed/`)
    - **GDPR:** `data/gdpr_rag_db.csv` — Article-level text with section numbers
    - **GLBA:** `data/glba_rag_db.xml` — Regulation text parsed from XML
    - **CCPA:** `data/ccpa_rag_db.csv` — California Civil Code §1798 sections
    - **COPPA:** `data/coppa_rag_db.xml` — Children's Online Privacy regulations
    - **SOX:** `data/sox_rag_db.csv` — Sarbanes-Oxley §302/§404 provisions
    """)

with col2:
    st.markdown("""
    <div class="callout pro">
    ✓ Grounded in actual regulatory text, not training data<br>
    ✓ Cites real section numbers from retrieved content<br>
    ✓ Handles regulatory updates — just re-index the new text<br>
    ✓ No formal engine needed
    </div>
    <div class="callout con">
    ✗ Still an LLM reasoning step — can misinterpret retrieved text<br>
    ✗ Retrieval quality matters: wrong chunks → wrong answer<br>
    ✗ No logical guarantees about completeness<br>
    ✗ Index build time on first run
    </div>
    <div class="callout note">
    ⚠ Best for questions about sections not yet formalized in Souffle 
    (§164.520, §164.528, §164.530, etc.)
    </div>
    """, unsafe_allow_html=True)

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 3: Formal Souffle
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## Strategy 3 — Formal Souffle Datalog Engine")

col1, col2 = st.columns([3, 2])

with col1:
    st.markdown("""
    **What it does:**
    Translates the user's question into formal logical facts (Datalog), runs them
    through a symbolic compliance engine that encodes the active regulation as logical
    rules, and produces a verdict with a machine-checkable proof tree.

    **How it works:**
    """)

    st.markdown("""
    <div class="pipe">
      <div class="pipe-box">User question</div>
      <div class="pipe-arr">→</div>
      <div class="pipe-box highlight">LLM1: Extractor<br><small>NL → Datalog facts</small></div>
      <div class="pipe-arr">→</div>
      <div class="pipe-box green">Souffle Engine<br><small>Symbolic reasoning</small></div>
      <div class="pipe-arr">→</div>
      <div class="pipe-box highlight">LLM2: Explainer<br><small>ADT tree → English</small></div>
      <div class="pipe-arr">→</div>
      <div class="pipe-box green">Answer + proof</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    **What is Souffle Datalog?**
    Souffle is a high-performance Datalog engine. Datalog is a *forward-chaining*
    logic programming language — unlike Prolog, it always terminates, has no
    function symbols, and evaluates queries in polynomial time. It is well-suited
    to encoding regulatory rules because regulations are naturally expressed as
    *conditional permissions*: "if A and B and C, then X is permitted."

    **How regulations are encoded:**
    Each regulatory section is a set of Datalog rules. For example, HIPAA §164.506(c)(2)
    is encoded as:
    ```prolog
    permitted_by_164_506_c_2(p1, p2, q, m, t, u) :-
        is_covered_entity(p1),
        is_health_care_provider(p2),
        is_phi(t),
        is_for_treatment(u).
    ```
    The top-level rule `is_disclosure_allowed(p1, p2, q, m, t, u, E)` derives
    permission by chaining through the section hierarchy. The `E` argument carries
    an **explanation tree** (an Algebraic Data Type in Souffle) that records exactly
    which rules fired.

    **The explanation tree** is the key differentiator. Every ALLOWED verdict comes
    with a machine-readable proof:
    ```
    §164.502(a): permitted use by covered entity
      └─ §164.502(a)(1)(ii): TPO per §164.506
            └─ §164.506(a): standard TPO
                  └─ §164.506(c)(2): treatment by health care provider ✓
    ```

    **Multi-regulation Soufflé engines** (all 6 supported):
    Each regulation has its own top-level `.dl` file and type hierarchy:
    - **HIPAA** — `hipaa_top.dl`: §164.502, §164.506, §164.508, §164.510, §164.512, §164.514, §164.524
    - **GDPR** — `gdpr_top.dl`: Art.6 (lawful basis), Art.17 (right to erasure)
    - **GLBA** — `glba_top.dl`: §313.x financial privacy provisions
    - **CCPA** — `ccpa_top.dl`: §1798.x consumer rights and data sharing
    - **COPPA** — `coppa_top.dl`: §312.x children's data protection
    - **SOX** — `sox_top.dl`: §302 (CEO/CFO certification), §404 (internal controls)

    All engines share the same bridge interface (`disclosure_attempted`, `is_disclosure_allowed`,
    `is_disclosure_denied`) so the pipeline is regulation-agnostic.

    **Closed-world assumption:**
    If no rule derives permission, the disclosure is DENIED. There is no "unknown"
    verdict — absence of proof is treated as denial. This is conservative but
    legally appropriate for a compliance tool.
    """)

with col2:
    st.markdown("""
    <div class="callout pro">
    ✓ Formal guarantees: if ALLOWED, a proof exists<br>
    ✓ Fully deterministic and reproducible<br>
    ✓ Machine-checkable proof tree (audit trail)<br>
    ✓ Persistent run artifacts for every query<br>
    ✓ No LLM reasoning in the compliance step
    </div>
    <div class="callout con">
    ✗ Coverage limited to formalized sections<br>
    ✗ LLM1 extraction can introduce errors<br>
    ✗ Requires Souffle installed locally<br>
    ✗ Can return UNKNOWN if LLM1 uses wrong string constants
    </div>
    <div class="callout key">
    🔑 This is the primary strategy for production compliance checking. 
    The formal proof is what makes it defensible.
    </div>
    """, unsafe_allow_html=True)

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 4: Agentic
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## Strategy 4 — Agentic Multi-Step Pipeline")

col1, col2 = st.columns([3, 2])

with col1:
    st.markdown("""
    **What it does:**  
    Decomposes the compliance check into specialized sub-tasks, each handled by a 
    dedicated agent call. Adds self-correction: if Souffle returns UNKNOWN, 
    Agent D diagnoses the problem and retries.

    **How it works:**
    """)

    st.markdown("""
    <div class="pipe">
      <div class="pipe-box highlight">Agent A<br><small>Entity extract</small></div>
      <div class="pipe-arr">→</div>
      <div class="pipe-box highlight">Agent B<br><small>Section mapper</small></div>
      <div class="pipe-arr">→</div>
      <div class="pipe-box highlight">Agent C<br><small>Facts validator</small></div>
      <div class="pipe-arr">→</div>
      <div class="pipe-box green">Souffle</div>
      <div class="pipe-arr">→</div>
      <div class="pipe-box purple">Agent D<br><small>Self-correct</small></div>
      <div class="pipe-arr">→</div>
      <div class="pipe-box highlight">Agent E<br><small>Explain</small></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    **The five agents:**
    
    | Agent | Role | Input | Output |
    |-------|------|-------|--------|
    | **A — Extractor** | Pulls entities from the question | Natural language | Partial JSON (sender, receiver, attribute, purpose) |
    | **B — Mapper** | Identifies relevant HIPAA sections | Entities + question | Section list + likely verdict |
    | **C — Validator** | Enforces valid Souffle string constants | Agent A output | Complete, validated DatalogScenario JSON |
    | **D — Resolver** | Diagnoses UNKNOWN and fixes it | Facts + Souffle output | Corrected JSON |
    | **E — Explainer** | Translates formal result to English | Souffle verdict + tree | Plain English answer |
    
    **Why the split matters:**  
    Strategy 3 uses a single LLM call (LLM1) for extraction. A single prompt must 
    simultaneously understand the question, select valid roles, choose the right 
    attribute, set oracle predicates, and populate extra_facts. This is a lot to 
    ask in one shot. The agentic approach separates concerns:
    
    - Agent A focuses only on "who and what"
    - Agent B focuses on "which law applies"  
    - Agent C acts as a type-checker against the Souffle hierarchy
    - Agent D provides a feedback loop when Souffle rejects the input
    
    **Self-correction (Agent D):**  
    When Souffle returns UNKNOWN (no matching output row), it usually means 
    a string constant mismatch — LLM used `"physician"` instead of `"doctor"`, 
    or `"healthcare"` instead of `"healthcare-operations"`. Agent D sees the 
    generated Datalog facts and the Souffle output, identifies the mismatch, 
    and produces a corrected JSON. Up to 2 retries.
    
    **Tradeoff:**  
    The agentic pipeline makes 4–6 LLM calls per question vs 2 for Strategy 3. 
    It is slower and more expensive, but significantly more robust on difficult 
    questions where extraction is ambiguous. It is the recommended strategy for 
    batch evaluation where accuracy matters more than speed.
    """)

with col2:
    st.markdown("""
    <div class="callout pro">
    ✓ Most robust extraction — separation of concerns<br>
    ✓ Self-correcting on UNKNOWN verdicts<br>
    ✓ Agent trace visible for debugging<br>
    ✓ Best accuracy on ambiguous questions<br>
    ✓ Same formal proof as Strategy 3
    </div>
    <div class="callout con">
    ✗ 4–6 LLM calls per question (slowest)<br>
    ✗ Most expensive (token cost)<br>
    ✗ More failure points<br>
    ✗ Still limited to formalized Souffle sections
    </div>
    <div class="callout note">
    ⚠ Best for batch evaluation and complex questions. 
    For interactive use, Strategy 3 (Formal) offers a better latency/accuracy balance.
    </div>
    """, unsafe_allow_html=True)

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Comparison Table
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## Comparison Table")

st.markdown("""
<table class="cmp">
<thead>
<tr>
  <th>Dimension</th>
  <th>1 · Baseline</th>
  <th>2 · RAG</th>
  <th>3 · Formal (Souffle)</th>
  <th>4 · Agentic</th>
</tr>
</thead>
<tbody>
<tr>
  <td><strong>Verdict source</strong></td>
  <td>LLM reasoning</td>
  <td>LLM over retrieved text</td>
  <td>Symbolic logic engine</td>
  <td>Symbolic logic engine</td>
</tr>
<tr>
  <td><strong>Formal guarantees</strong></td>
  <td><span class="cross">✗ None</span></td>
  <td><span class="cross">✗ None</span></td>
  <td><span class="check">✓ Proof tree</span></td>
  <td><span class="check">✓ Proof tree</span></td>
</tr>
<tr>
  <td><strong>Deterministic</strong></td>
  <td><span class="cross">✗ Non-deterministic</span></td>
  <td><span class="partial">~ Retrieval deterministic, reasoning not</span></td>
  <td><span class="check">✓ Fully deterministic</span></td>
  <td><span class="check">✓ Souffle step is</span></td>
</tr>
<tr>
  <td><strong>Legal coverage</strong></td>
  <td>All 6 regulations (training data)</td>
  <td>All indexed sections (per regulation)</td>
  <td>Formalized sections per regulation</td>
  <td>Formalized sections per regulation</td>
</tr>
<tr>
  <td><strong>Handles unformalized sections</strong></td>
  <td><span class="check">✓ Yes</span></td>
  <td><span class="check">✓ Yes (if indexed)</span></td>
  <td><span class="cross">✗ Returns DENIED (conservative)</span></td>
  <td><span class="cross">✗ Returns DENIED (conservative)</span></td>
</tr>
<tr>
  <td><strong>LLM calls per question</strong></td>
  <td>1</td>
  <td>1 (+ retrieval)</td>
  <td>2 (LLM1 + LLM2)</td>
  <td>4–6 (A+B+C+E ± D)</td>
</tr>
<tr>
  <td><strong>Typical latency</strong></td>
  <td>~5–10s</td>
  <td>~7–15s (+ index build on first run)</td>
  <td>~10–15s</td>
  <td>~20–40s</td>
</tr>
<tr>
  <td><strong>Audit trail</strong></td>
  <td><span class="cross">✗ None</span></td>
  <td><span class="partial">~ Section references only</span></td>
  <td><span class="check">✓ Full run artifacts + proof tree</span></td>
  <td><span class="check">✓ Full artifacts + agent trace</span></td>
</tr>
<tr>
  <td><strong>Self-correcting</strong></td>
  <td><span class="cross">✗ No</span></td>
  <td><span class="cross">✗ No</span></td>
  <td><span class="cross">✗ No</span></td>
  <td><span class="check">✓ Agent D retries on UNKNOWN</span></td>
</tr>
<tr>
  <td><strong>Setup required</strong></td>
  <td>API key only</td>
  <td>API key + index build</td>
  <td>API key + Souffle binary</td>
  <td>API key + Souffle binary</td>
</tr>
<tr>
  <td><strong>Recommended for</strong></td>
  <td>Quick answers, edge cases, comparison baseline</td>
  <td>Questions on unformalized sections, regulatory updates</td>
  <td>Production use, interactive queries</td>
  <td>Batch eval, complex questions, highest accuracy</td>
</tr>
</tbody>
</table>
""", unsafe_allow_html=True)

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Design Rationale
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## Design Rationale: Why Not Just Use an LLM?")

st.markdown("""
Healthcare compliance is a domain where errors have legal consequences. A nurse 
who discloses patient records based on incorrect advice faces HIPAA sanctions. 
A hospital that relies on an LLM that confidently but wrongly answers "PERMITTED" 
faces civil and criminal penalties.

**The core problem with pure LLM compliance checking:**

1. **Hallucination:** LLMs can cite §164.502(a)(1)(ii) for a scenario that is 
   actually governed by §164.508(a)(3). The citation looks correct but the 
   reasoning is wrong.

2. **Inconsistency:** The same question rephrased slightly may produce a different 
   verdict. Compliance decisions need to be reproducible.

3. **No audit trail:** "The AI said it was OK" is not a legal defense. Compliance 
   requires documentation of the specific rule that permitted a disclosure.

4. **Adversarial vulnerability:** A carefully phrased question can steer an LLM 
   to a desired verdict. A logic engine cannot be persuaded.

**Why Souffle Datalog specifically:**

Datalog is a restricted form of logic programming that always terminates and has 
no function symbols — making it significantly easier to verify than Prolog or 
general theorem provers. HIPAA's conditional structure maps naturally to Datalog 
rules. The formalization draws directly from the academic work of Sarne et al. 
(*HIPAA_FORMALIZATION.pdf*), which provides a first-order temporal logic encoding 
that we translate to Souffle using Kamp-style temporal flattening.

**Why LLMs are still necessary:**

HIPAA questions come in natural language. Souffle takes structured facts. 
The "translation gap" between them is where LLMs are genuinely useful — not for 
reasoning about law, but for *parsing* a human question into the precise formal 
vocabulary that the logic engine understands. LLM2 performs the inverse translation: 
it makes the formal proof tree readable to non-experts.

This separation — *LLMs for translation, logic for reasoning* — is the core 
architectural principle of ComplianceGPT.
""")

st.divider()

st.markdown("## Coverage and Limitations")

st.markdown("### HIPAA (45 CFR Part 164)")
col_a, col_b = st.columns(2)
with col_a:
    st.markdown("""
    **Currently formalized (Souffle):**
    - §164.502 — General rules for PHI use/disclosure
    - §164.506 — Treatment, payment, healthcare operations (TPO)
    - §164.508 — Authorization requirements (marketing, psychotherapy notes)
    - §164.510 — Opportunity to agree or object (facility directories, family)
    - §164.512 — Public interest disclosures (law enforcement, public health, research)
    - §164.514 — De-identification, limited data sets
    - §164.524 — Individual right of access
    """)

with col_b:
    st.markdown("""
    **Declared as stubs (conservative denial):**
    - §164.520 — Notice of privacy practices
    - §164.522 — Right to request restrictions
    - §164.528 — Accounting of disclosures
    - §164.530 — Administrative requirements

    **Not in scope (regulatory):**
    - §164.308–316 — Security Rule (administrative/technical safeguards)
    - §164.400–414 — Breach Notification Rule
    - State law preemption analysis
    """)

st.markdown("### Other Regulations")
col_c, col_d = st.columns(2)
with col_c:
    st.markdown("""
    **GDPR (EU General Data Protection Regulation):**
    - Art. 6 — Lawful basis for processing
    - Art. 17 — Right to erasure ("right to be forgotten")

    **GLBA (Gramm-Leach-Bliley Act):**
    - §313.x — Financial privacy and opt-out provisions
    - NPI sharing with affiliated and non-affiliated third parties

    **CCPA (California Consumer Privacy Act):**
    - §1798.x — Consumer rights (access, deletion, opt-out of sale)
    - Data sharing for business purposes vs. sale
    """)

with col_d:
    st.markdown("""
    **COPPA (Children's Online Privacy Protection Act):**
    - §312.x — Verifiable parental consent requirements
    - Collection from children under 13, educational context exceptions

    **SOX (Sarbanes-Oxley Act):**
    - §302 — CEO/CFO certification of financial reports
    - §404 — Management assessment and auditor attestation of internal controls

    All non-HIPAA engines use the same bridge interface and share the
    same 4-strategy pipeline (baseline, RAG, formal, agentic).
    """)

st.markdown("""
<div class="callout note">
⚠ <strong>Disclaimer:</strong> ComplianceGPT is a research and educational tool. 
It is not a substitute for legal advice. HIPAA compliance determinations in 
clinical or operational contexts should be reviewed by a qualified healthcare 
attorney or compliance officer.
</div>
""", unsafe_allow_html=True)
