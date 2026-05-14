"""
strategies/rag.py — Strategy 2: RAG with hybrid BM25 + semantic retrieval.
Routes through ModelClient. No hardcoded Anthropic. temperature=0.0.

Knowledge base priority (first with .txt files):
  data/ecfr_parsed/ → datalog_engine/ecfr_text/ → data/
"""

import os, re, time, json
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

try:
    from connector.model_client import ModelClient
    from connector.settings import get_settings
    from connector import config
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from connector.model_client import ModelClient
    from connector.settings import get_settings
    from connector import config


# ── Document model ────────────────────────────────────────────────────────────
@dataclass
class Document:
    doc_id: str; text: str; source: str; section: str = ""

def _section(stem): m=re.search(r'(\d{3})[_.](\d+)',stem); return f"{m.group(1)}.{m.group(2)}" if m else ""

def load_kb(paths):
    docs = []
    for p in paths:
        p=Path(p)
        if p.is_dir():
            for f in sorted(p.rglob("*.txt")): docs.extend(_load(f))
            for f in sorted(p.rglob("*.md")):  docs.extend(_load(f))
        elif p.is_file(): docs.extend(_load(p))
    return docs

# Multi-regulation citation patterns
_CITATION_PATTERNS = [
    r'164\.\d+(?:\([a-z0-9]+\))*',            # HIPAA §164.xxx
    r'Art\.?\s*\d+(?:\(\d+\))?(?:\([a-z]\))?', # GDPR Art.6(1)(a)
    r'§\s*313\.\d+(?:\([a-z0-9]+\))*',         # GLBA §313.x
    r'§\s*1798\.\d+(?:\([a-z0-9]+\))*',         # CCPA §1798.x
    r'§\s*31[0-9]\.\d+(?:\([a-z0-9]+\))*',      # COPPA §312.x
    r'§\s*30[234]\b', r'§\s*40[24]\b',          # SOX §302, §404
]

def _extract_citations(text):
    import re as _re
    found = set()
    for pat in _CITATION_PATTERNS:
        found.update(_re.findall(pat, text, _re.IGNORECASE))
    return sorted(found)

def _load(path):
    path = Path(path)
    # CSV regulation database
    if path.suffix == ".csv":
        return _load_csv(path)
    # XML regulation database
    if path.suffix == ".xml":
        return _load_xml(path)
    try: text=path.read_text(encoding="utf-8",errors="replace").strip()
    except: return []
    if not text: return []
    sec = _section(path.stem)
    return [Document(doc_id=f"{path.stem}_{i}",text=c,source=path.name,section=sec)
            for i,c in enumerate(_chunk(text))]

def _load_csv(path):
    """Load a regulation CSV database (columns: id, section_number, original_text/natural_language)."""
    import csv as _csv
    docs = []
    try:
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            reader = _csv.DictReader(f)
            for row in reader:
                text = row.get("original_text") or row.get("natural_language") or ""
                text = text.strip()
                if not text:
                    continue
                sec = row.get("section_number", row.get("id", ""))
                docs.append(Document(
                    doc_id=row.get("id", f"{path.stem}_{len(docs)}"),
                    text=text, source=path.name, section=str(sec),
                ))
    except Exception:
        pass
    return docs

def _load_xml(path):
    """Load a regulation XML database — extract text from all text-bearing elements."""
    import xml.etree.ElementTree as ET
    docs = []
    try:
        tree = ET.parse(path)
        for i, elem in enumerate(tree.iter()):
            text = (elem.text or "").strip()
            if len(text) > 50:
                section = elem.get("num", elem.get("id", ""))
                docs.append(Document(
                    doc_id=f"{path.stem}_{i}", text=text,
                    source=path.name, section=section,
                ))
    except Exception:
        pass
    return docs

def _chunk(text,max_w=600):
    paras=[p.strip() for p in re.split(r'\n{2,}',text) if p.strip()]
    chunks,cur,n=[],[],0
    for p in paras:
        w=len(p.split())
        if n+w>max_w and cur: chunks.append("\n\n".join(cur)); cur,n=[],0
        cur.append(p); n+=w
    if cur: chunks.append("\n\n".join(cur))
    return chunks or [text]

def _focused_query(question: str, max_words: int = 75) -> str:
    """Return a focused retrieval query from a long narrative.

    Goldcoin/PrivacyCI questions are 200+ words of background narrative.
    Feeding the full text to BM25 matches generic HIPAA terms throughout and
    consistently surfaces 164.502 (the general restriction) instead of the
    specific exception section that governs the scenario. Using the last 3
    sentences — which describe the specific disclosure action — focuses
    retrieval on the relevant exception.
    """
    words = question.split()
    if len(words) <= max_words:
        return question
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', question.strip()) if s.strip()]
    if len(sentences) <= 3:
        return " ".join(words[-max_words:])
    return " ".join(sentences[-3:])


# ── Indices ───────────────────────────────────────────────────────────────────
def _tok(text): return re.findall(r'\b\w+\b',text.lower())

class BM25Index:
    def __init__(self,docs):
        from rank_bm25 import BM25Okapi
        self.docs=docs; self.bm25=BM25Okapi([_tok(d.text) for d in docs])
    def scores(self,q): return self.bm25.get_scores(_tok(q)).tolist()

class SemanticIndex:
    def __init__(self,docs):
        try:
            from sentence_transformers import SentenceTransformer
            self.model=SentenceTransformer("all-MiniLM-L6-v2")
            self.emb=self.model.encode([d.text for d in docs],show_progress_bar=False,normalize_embeddings=True)
            self.docs=docs; self.available=True
        except ImportError: self.available=False
    def scores(self,q):
        if not self.available: return [0.0]*len(self.docs)
        qe=self.model.encode([q],normalize_embeddings=True)
        return (self.emb@qe.T).flatten().tolist()

def _norm(s):
    mn,mx=min(s),max(s)
    return [0.0]*len(s) if mx==mn else [(x-mn)/(mx-mn) for x in s]

def hybrid_retrieve(q,bm25,sem,k=5,alpha=0.5):
    sc=[alpha*a+(1-alpha)*b for a,b in zip(_norm(sem.scores(q)),_norm(bm25.scores(q)))]
    ranked=sorted(range(len(bm25.docs)),key=lambda i:sc[i],reverse=True)
    return [(bm25.docs[i],sc[i]) for i in ranked[:k]]


# ── Prompt ────────────────────────────────────────────────────────────────────
_FEW_SHOT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "few_shot_hipaa.json"

def _load_few_shot():
    try:
        with open(_FEW_SHOT_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

_SEP = "\n" + "─" * 60 + "\n"

def _format_example_rag(ex: dict) -> str:
    steps = "\n".join(f"  Step {i+1} — {s}" for i, s in enumerate(ex["reasoning_steps"]))
    v_sym = "✅ PERMITTED" if ex["verdict"] == "PERMITTED" else "❌ DENIED"
    return (
        f"QUESTION: {ex['question']}\n\n"
        f"RETRIEVED CONTEXT:\n{ex['rag_context_snippet']}\n\n"
        f"REASONING:\n{steps}\n"
        f"**VERDICT: {v_sym}**"
    )

def _build_few_shot_block_rag() -> str:
    examples = _load_few_shot()
    if not examples:
        return ""
    parts = [_format_example_rag(e) for e in examples]
    return (
        "\nEXAMPLES (study these to learn how to reason from retrieved regulatory text):\n\n"
        + _SEP.join(parts)
        + "\n" + "─" * 60
        + "\n\nNow answer the following new question using the same reasoning process.\n"
    )

_COT_INSTRUCTION_RAG = (
    "\nANALYSIS PROCESS (show your work for each step in your answer):\n"
    "Step 1 — Action type: what PHI is disclosed, by whom, to whom, for what purpose?\n"
    "Step 2 — Section search: scan the REGULATORY CONTEXT for a section that EXPLICITLY PERMITS this action. Quote the provision.\n"
    "Step 3 — Exception check: confirm the permissive provision clearly covers this scenario.\n"
    "Step 4 — Verdict: PERMITTED if Step 3 confirmed an exception; DENIED if none was found.\n"
)

_ANALYSIS_PROCESS_DEFAULT = (
    "\nANALYSIS PROCESS:\n"
    "1. Identify the specific type of disclosure or action in the scenario.\n"
    "2. Search the retrieved text for a section that explicitly PERMITS this type of disclosure.\n"
    "3. If a permissive exception applies → PERMITTED. Only if no exception covers the scenario → DENIED.\n"
)

_REG_NAMES_RAG = {
    "hipaa": "HIPAA (45 CFR §164)",
    "gdpr":  "GDPR (EU General Data Protection Regulation)",
    "glba":  "GLBA (Gramm-Leach-Bliley Act)",
    "ccpa":  "CCPA (California Consumer Privacy Act)",
    "coppa": "COPPA (Children's Online Privacy Protection Act, 16 CFR §312)",
    "sox":   "SOX (Sarbanes-Oxley Act)",
}

def _build_system(regulation: str, style: str = "zero_shot") -> str:
    name    = _REG_NAMES_RAG.get(regulation, regulation.upper())
    process = _COT_INSTRUCTION_RAG if style in ("cot", "few_shot_cot") else _ANALYSIS_PROCESS_DEFAULT
    fs      = _build_few_shot_block_rag() if style in ("few_shot", "few_shot_cot") else ""
    return (
        f"You are a regulatory compliance expert specializing in {name}.\n\n"
        f"The retrieved context contains {name} regulatory text — including both the general rule "
        f"(which requires authorization by default) AND specific EXCEPTION sections that explicitly "
        f"permit certain disclosures without authorization.\n"
        f"{process}{fs}\n"
        f"VERDICT RULE (mandatory): Output ONLY ✅ PERMITTED or ❌ DENIED. Never \"Depends\", "
        f"\"Conditional\", or \"Unable to Determine\".\n\n"
        f"**VERDICT: [✅ PERMITTED / ❌ DENIED]**\n"
        f"**Answer:** [Direct answer citing the specific {name} section that governs this case.]\n"
        f"**Legal Basis:** [The specific permissive or restrictive provision from the retrieved text.]\n"
        f"**Conditions or Exceptions:** [Only if applicable.]"
    )

def _build_prompt(q,retrieved):
    ctx="\n\n---\n\n".join(
        f"[§{d.section}|{d.source}|score:{s:.2f}]\n{d.text}" if d.section
        else f"[{d.source}|score:{s:.2f}]\n{d.text}"
        for d,s in retrieved
    )
    # Question-first so small-context models (e.g. Llama-2, 4K ctx) never have
    # it truncated or attention-diluted by prepended regulatory text.
    return f"QUESTION: {q}\n\n---\n\nREGULATORY CONTEXT:\n\n{ctx}"


# ── Result ────────────────────────────────────────────────────────────────────
@dataclass
class RAGResult:
    strategy:str="rag"; question:str=""; verdict:str=""; answer:str=""
    citations:list=field(default_factory=list); retrieved_docs:list=field(default_factory=list)
    latency_seconds:float=0.0; alpha:float=0.5; k:int=5; kb_size:int=0
    error:str=""; model:str=""; provider:str=""; llm_raw:str=""

_AMBIGUOUS_WORDS = ("DEPENDS", "CONDITIONAL", "UNABLE TO", "UNCERTAIN", "UNCLEAR",
                    "CONTEXT-DEPENDENT", "CASE-BY-CASE")

def _verdict(t):
    import re as _re
    # Priority 1: check the structured VERDICT line (avoids false matches in body text)
    m = _re.search(r'\*{0,2}VERDICT:?\*{0,2}\s*([^\n]{0,80})', t, _re.IGNORECASE)
    if m:
        line = m.group(1).upper()
        # If LLM ignored the binary-verdict rule and output an ambiguous answer, default DENIED
        if any(w in line for w in _AMBIGUOUS_WORDS): return "DENIED"
        if "✅" in line or ("PERMITTED" in line and "NOT PERMITTED" not in line): return "PERMITTED"
        if "❌" in line or "DENIED" in line or "NOT PERMITTED" in line: return "DENIED"
    # Priority 2: first 120 chars (verdict usually appears at top of response)
    first = t[:120].upper()
    if "✅" in first: return "PERMITTED"
    if "❌" in first: return "DENIED"
    if "PERMITTED" in first and "NOT PERMITTED" not in first: return "PERMITTED"
    if "DENIED" in first or "NOT PERMITTED" in first: return "DENIED"
    # Priority 3: full-text scan (lower confidence fallback)
    u = t.upper()
    if "✅" in u or ("PERMITTED" in u and "NOT PERMITTED" not in u): return "PERMITTED"
    if "❌" in u or "DENIED" in u or "NOT PERMITTED" in u: return "DENIED"
    return "DENIED"  # default-deny for ambiguous output

def _find_kb(regulation="hipaa"):
    """Return knowledge-base paths for the given regulation."""
    root = Path(config.DATALOG_ENGINE_DIR).parent
    data = root / "data"
    engine_ecfr = Path(config.DATALOG_ENGINE_DIR) / "ecfr_text"

    # Regulation-specific CSV/XML databases
    _REG_DB = {
        "gdpr":  data / "gdpr_rag_db.csv",
        "glba":  data / "glba_rag_db.xml",
        "ccpa":  data / "ccpa_rag_db.csv",
        "coppa": data / "coppa_rag_db.xml",
        "sox":   data / "sox_rag_db.csv",
    }

    if regulation != "hipaa" and regulation in _REG_DB:
        db = _REG_DB[regulation]
        if db.exists():
            return [str(db)]

    # HIPAA: use the parsed eCFR text files
    candidates = [data / "ecfr_parsed", data / "ecfr_text", engine_ecfr, data]
    return [str(p) for p in candidates if p.exists() and any(p.glob("*.txt"))]


# ── Context-window lookup ─────────────────────────────────────────────────────
# True context limits for models with non-standard windows. Used to cap k so
# retrieved docs never overflow the model's context.
_MODEL_CTX_LIMITS = {
    "llama2": 4096, "llama2:7b": 4096, "llama2:13b": 4096,
    "llama3": 8192, "llama3.1": 8192,
    "mistral": 32768, "mixtral": 32768,
    "deepseek-r1": 64000,
    "gemma": 8192,
}

def _ctx_for_model(model: str) -> int:
    """Return the effective context window (tokens) for a given model tag."""
    m = model.lower()
    for key, ctx in _MODEL_CTX_LIMITS.items():
        if key in m:
            return ctx
    return 32768


# ── Strategy ──────────────────────────────────────────────────────────────────
class RAGStrategy:
    def __init__(self,knowledge_base_paths=None,k=5,alpha=0.5,api_key=None,model=None,
                 prompt_style: str = "zero_shot"):
        s = get_settings()
        if model and "/" in str(model):
            parts=str(model).split("/",1); self._provider,self._model=parts[0],parts[1]
        elif model: self._provider,self._model=s["llm1_provider"],str(model)
        else:       self._provider,self._model=s["llm1_provider"],s["llm1_model"]
        self._api_key=api_key; self.alpha=alpha; self._built=False
        self._style=prompt_style
        regulation = s.get("active_regulation", "hipaa")
        self.kb_paths=knowledge_base_paths or _find_kb(regulation)
        ctx_win = _ctx_for_model(self._model)
        max_k = max(1, (ctx_win - 800) // 400)
        self.k = min(k, max_k)

    def _call(self, user, max_tokens=1200, system: str = ""):
        return ModelClient(
            provider=self._provider, model=self._model, api_key=self._api_key
        ).complete(system=system, user=user, max_tokens=max_tokens)

    def build_index(self):
        if self._built: return
        if not self.kb_paths:
            raise ValueError(
                "No knowledge base found. Run:\n"
                "  python scripts/parse_ecfr_xml.py --api --out data/ecfr_parsed")
        print(f"  [RAG] Loading from: {self.kb_paths}")
        self.docs=load_kb(self.kb_paths)
        if not self.docs: raise ValueError(f"No .txt files in {self.kb_paths}")
        print(f"  [RAG] {len(self.docs)} chunks indexed.")
        self.bm25=BM25Index(self.docs); self.sem=SemanticIndex(self.docs)
        if not self.sem.available: print("  [RAG] BM25-only (no sentence-transformers)"); self.alpha=0.0
        self._built=True

    def run(self,question):
        if not self._built: self.build_index()
        t0=time.time()
        regulation = get_settings().get("active_regulation", "hipaa")
        system = _build_system(regulation, self._style)
        try:
            retrieval_q=_focused_query(question)
            retrieved=hybrid_retrieve(retrieval_q,self.bm25,self.sem,self.k,self.alpha)
            prompt=_build_prompt(question,retrieved)
            answer=self._call(prompt, system=system)
            return RAGResult(
                question=question, verdict=_verdict(answer), answer=answer,
                citations=_extract_citations(answer),
                retrieved_docs=[{"doc_id":d.doc_id,"source":d.source,"section":d.section,"score":round(s,3)}
                                for d,s in retrieved],
                latency_seconds=round(time.time()-t0,2),alpha=self.alpha,k=self.k,
                kb_size=len(self.docs),model=self._model,provider=self._provider,
                llm_raw=answer,
            )
        except Exception as e:
            return RAGResult(question=question,verdict="ERROR",error=str(e),
                             latency_seconds=round(time.time()-t0,2),
                             model=self._model,provider=self._provider)
