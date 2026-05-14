"""
app/streamlit_app.py — ComplianceGPT
Single-file multipage app. Navigation via sidebar radio (no pages/ folder needed).
Run: streamlit run app/streamlit_app.py

All pages: Compliance Checker | Methodology | Batch Eval | Settings
Settings values (model, strategies, regulation) flow into the Checker page.
All LLM calls use temperature=0.0.
"""

import sys, os, io, csv, json, re, time
from pathlib import Path
from datetime import datetime
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(
    page_title="ComplianceGPT",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from connector.settings import get_settings, MODEL_REGISTRY
import subprocess, os

def install_souffle():
    if os.path.exists("/usr/local/bin/souffle"):
        return
    subprocess.run([
        "bash", "-c",
        """
        wget -q https://github.com/souffle-lang/souffle/releases/download/2.5/\
souffle_2.5_amd64.deb -O /tmp/souffle.deb &&
        dpkg -i /tmp/souffle.deb || apt-get install -f -y
        """
    ], check=True)

install_souffle()
# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html,body,[class*="css"]{ font-family:'IBM Plex Sans',sans-serif; font-size:.92rem; }
.stApp,.main,.block-container{ background:#ffffff !important; }
[data-testid="stSidebar"]{ background:#f8f9fa !important; border-right:1px solid #dee2e6; }
[data-testid="stSidebar"] *{ color:#212529 !important; }
h1{ font-family:'IBM Plex Mono',monospace; color:#1a1a2e; font-size:1.4rem; }
h2{ color:#1a1a2e; font-size:1.15rem; margin-top:24px; }
h3{ color:#495057; font-size:1rem; }
p,li,label{ color:#212529; }
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li{ color:#212529; font-size:.92rem; }
textarea,input[type="text"]{ background:#f8f9fa !important; color:#212529 !important;
  border:1.5px solid #ced4da !important; border-radius:6px !important; font-size:.92rem !important; }
textarea:focus,input:focus{ border-color:#334155 !important; }
.stButton>button{ background:#ffffff !important; color:#334155 !important;
  border:1.5px solid #94a3b8 !important; border-radius:6px !important;
  font-family:'IBM Plex Mono',monospace !important;
  font-weight:600 !important; font-size:0.84rem !important; }
.stButton>button:hover{ background:#f1f5f9 !important; border-color:#334155 !important; color:#1e293b !important; }
[data-testid="stExpander"]{ border:1px solid #dee2e6 !important; border-radius:6px !important; }
[data-testid="stExpander"] summary{ color:#334155 !important; font-weight:600; }
pre,code{ background:#f1f3f5 !important; color:#212529 !important;
  border:1px solid #dee2e6 !important; border-radius:4px !important;
  font-family:'IBM Plex Mono',monospace !important; font-size:0.8rem !important; }
[data-testid="stTabs"] button{ color:#6c757d !important; font-size:.88rem !important; }
[data-testid="stTabs"] button[aria-selected="true"]{ color:#334155 !important;
  border-bottom:2px solid #334155 !important; }
hr{ border-color:#dee2e6 !important; }
label{ color:#212529 !important; font-size:.9rem !important; }
.rc{ border:1.5px solid #dee2e6; border-radius:8px; padding:14px 16px;
  background:#fff; margin:4px 0; min-height:88px; }
.rc.allowed{ border-color:#198754; background:#f0fdf4; }
.rc.denied{ border-color:#dc3545; background:#fff5f5; }
.rc.error{ border-color:#fd7e14; background:#fffbf5; }
.rc.running{ border-color:#6366f1; background:#f5f3ff; }
.rc.pending{ border-color:#dee2e6; background:#f8f9fa; }
.ct{ font-family:'IBM Plex Mono',monospace; font-size:.72rem; font-weight:600;
  color:#6c757d; text-transform:uppercase; letter-spacing:.4px; margin-bottom:5px; }
.va{ font-weight:700; } .va.allowed{ color:#198754; } .va.denied{ color:#dc3545; }
.va.error{ color:#fd7e14; } .va.running{ color:#6366f1; } .va.unknown{ color:#6c757d; }
.pill{ display:inline-block; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:12px;
  padding:1px 9px; font-family:'IBM Plex Mono',monospace; font-size:.72rem; color:#334155; margin:2px; }
.cmp{ width:100%; border-collapse:collapse; }
.cmp th{ background:#f1f3f5; border:1px solid #dee2e6; padding:8px 12px;
  font-family:'IBM Plex Mono',monospace; font-size:.76rem; font-weight:600; color:#495057; text-align:left; }
.cmp td{ border:1px solid #dee2e6; padding:8px 12px; font-size:.85rem; vertical-align:top; color:#212529; }
.cmp tr:hover td{ background:#f8f9fa; }
.ca{ color:#198754; font-weight:700; } .cd{ color:#dc3545; font-weight:700; }
.ce{ color:#fd7e14; font-weight:700; }
.ag-y{ color:#198754; font-weight:600; } .ag-n{ color:#dc3545; font-weight:600; }
.cu{ background:#e2e8f0; border-radius:12px 12px 2px 12px; padding:10px 14px; margin:6px 0 6px 60px; color:#212529; }
.cb{ background:#f8f9fa; border:1px solid #dee2e6; border-radius:12px 12px 12px 2px; padding:10px 14px; margin:6px 60px 6px 0; color:#212529; }
.clabel{ font-family:'IBM Plex Mono',monospace; font-size:.7rem; color:#6c757d; margin-bottom:3px; }
.tree-section{ font-family:'IBM Plex Mono',monospace; font-size:.8rem; color:#334155; font-weight:600; }
.tree-leaf{ font-family:'IBM Plex Mono',monospace; font-size:.78rem; color:#198754; }
.tree-indent{ margin-left:20px; border-left:2px solid #dee2e6; padding-left:10px; }
.callout{ border-radius:6px; padding:12px 16px; margin:10px 0; font-size:.88rem; }
.callout.pro{ background:#d1e7dd; border-left:4px solid #198754; color:#0a3622; }
.callout.con{ background:#f8d7da; border-left:4px solid #dc3545; color:#58151c; }
.callout.note{ background:#fff3cd; border-left:4px solid #ffc107; color:#664d03; }
.callout.key{ background:#f8fafc; border-left:4px solid #334155; color:#1e293b; }
.pipe{ display:flex; align-items:center; gap:8px; margin:12px 0; flex-wrap:wrap;
  font-family:'IBM Plex Mono',monospace; font-size:.8rem; }
.pb{ background:#f1f3f5; border:1px solid #dee2e6; border-radius:6px; padding:6px 12px; color:#212529; white-space:nowrap; }
.pb.h{ background:#e2e8f0; border-color:#94a3b8; color:#334155; }
.pb.g{ background:#d1e7dd; border-color:#a3cfbb; color:#0a3622; }
.pa{ color:#adb5bd; font-size:1rem; }
.section-header{ font-family:'IBM Plex Mono',monospace; font-size:.75rem; font-weight:600;
  color:#6c757d; text-transform:uppercase; letter-spacing:.5px; margin-top:20px; margin-bottom:6px; }
.stat-box{ border:1px solid #dee2e6; border-radius:8px; padding:16px; text-align:center; background:#f8f9fa; }
.stat-num{ font-family:'IBM Plex Mono',monospace; font-size:2rem; font-weight:700; color:#1a1a2e; }
.stat-label{ color:#6c757d; font-size:.8rem; margin-top:2px; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

REGULATIONS = {
    "hipaa": "🏥 HIPAA — US Healthcare Privacy",
    "gdpr":  "🇪🇺 GDPR — EU Data Protection",
    "ccpa":  "🌴 CCPA — California Privacy",
    "glba":  "🏦 GLBA — Financial Privacy",
    "sox":   "📊 SOX — Financial Reporting",
    "coppa": "👶 COPPA — Children's Online Privacy",
}

REG_STUB = {}  # All regulations now support all 4 strategies

STRAT_LABELS = {
    "baseline": "1 · Baseline LLM",
    "rag":      "2 · RAG",
    "formal":   "3 · Formal (Souffle)",
    "agentic":  "4 · Agentic",
}

EXAMPLES = {
    "hipaa": [
        "Can I see my lab results before my doctor reviews them?",
        "Can a hospital share records with a marketing company?",
        "Can my insurer get my diagnosis for billing?",
        "Can a nurse report suspected child abuse to authorities?",
        "Can my psychiatrist share therapy notes with my GP?",
        "Can my doctor share my HIV status with my employer?",
    ],
    "gdpr": [
        "Can a company send marketing emails to EU users who gave explicit consent?",
        "Can a healthcare provider process patient medical records to provide direct care?",
        "Can a user request deletion of their personal data after withdrawing consent?",
        "Can a company share EU user data with a third-party analytics firm without consent?",
    ],
    "glba": [
        "Can a bank share customer account information with an affiliated insurance company?",
        "Can a financial institution share NPI with a third-party servicer under a contract?",
        "Can a customer opt out of data sharing with unaffiliated third parties?",
        "Can a mortgage company share credit history with a joint marketer?",
    ],
    "ccpa": [
        "Can a California business share consumer personal information with a service provider?",
        "Can a business disclose consumer data as required by a state court order?",
        "Can a consumer request deletion of their personal data from a business?",
        "Can a business sell a minor's personal information without parental consent?",
    ],
    "sox":  [
        "Can a public company file its quarterly 10-Q when CEO and CFO have certified it?",
        "Can a CFO destroy financial audit records before the retention period expires?",
        "Can an auditor attest to internal controls with no known material weaknesses?",
        "Can a company file its annual report without a registered auditor attestation?",
    ],
    "coppa":[
        "Can an educational website collect a child's name and email for classroom use?",
        "Can a children's app collect device identifiers for internal analytics only?",
        "Can an operator collect a 10-year-old's data without verifiable parental consent?",
        "Can a school authorize data collection from students without direct parental notice?",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────

_defaults = {
    "page":           "Compliance Checker",
    "mode":           "single",
    "history":        [],
    "chat_messages":  [],
    "batch_results":  [],
    # RAG instances are keyed by regulation: rag_instance_<reg>
    # No static "rag_instance" key needed
}
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ─────────────────────────────────────────────────────────────────────────────
# ADT Tree
# ─────────────────────────────────────────────────────────────────────────────

def parse_tree(s):
    def split_top(text):
        parts, depth, cur = [], 0, []
        for ch in text:
            if ch == '(': depth += 1
            elif ch == ')': depth -= 1
            if ch == ',' and depth == 0:
                parts.append(''.join(cur).strip()); cur = []
            else:
                cur.append(ch)
        if cur: parts.append(''.join(cur).strip())
        return parts
    def parse(text):
        text = text.strip()
        if not text.startswith('$'):
            return {"type":"Raw","label":text,"children":[]}
        m = re.match(r'^\$(\w+)\((.+)\)$', text, re.DOTALL)
        if not m: return {"type":"Raw","label":text,"children":[]}
        ctor, inner = m.group(1), m.group(2)
        if ctor == "Leaf":
            return {"type":"Leaf","label":inner.strip().strip('"'),"children":[]}
        parts = split_top(inner)
        return {"type":ctor,"label":parts[0].strip().strip('"') if parts else "",
                "children":[parse(p) for p in parts[1:]]}
    return parse(s.strip())

def _tree_to_proof_lines(node, premises=None):
    """
    Convert parsed ADT tree into Datalog-style proof lines.
    Returns list of (premises_list, conclusion, rule_name) tuples.
    """
    if not node: return []
    t     = node.get("type","Raw")
    label = node.get("label","")
    ch    = node.get("children",[])

    # Extract section reference from label e.g. "164.502(a)(1)(i): disclosure..."
    m = re.match(r'(\d{3}\.\d+(?:\([^)]+\))*):?\s*(.*)', label)
    section = f"§{m.group(1)}" if m else label
    desc    = m.group(2).strip() if m else ""

    if t == "Leaf":
        return [([], section, desc)]

    # Recurse into children
    all_lines = []
    child_conclusions = []
    for c in ch:
        sub = _tree_to_proof_lines(c)
        all_lines.extend(sub)
        if sub:
            last = sub[-1]
            child_conclusions.append(last[1])  # conclusion of child subtree

    all_lines.append((child_conclusions, section, desc))
    return all_lines


def _render_proof_block(premises, conclusion, desc, rule_idx):
    """Render one inference step as horizontal-rule Datalog notation."""
    mono = "font-family:IBM Plex Mono,monospace;font-size:.78rem"
    if not premises:
        span_c = '<span style="color:#198754">'+chr(10003)+' '+conclusion+'</span>'
        span_d = '<span style="color:#6c757d;font-size:.7rem;margin-left:8px">'+desc+'</span>'
        return '<div style="margin:4px 0;' + mono + '">' + span_c + span_d + '</div>'

    bar_len = max(sum(len(p)+3 for p in premises), len(conclusion)+2, 20)
    bar     = chr(9472) * bar_len
    rule_label = "(R"+str(rule_idx)+")" if rule_idx else ""
    prem_html  = "".join('<span style="color:#495057;margin-right:16px">'+p+'</span>' for p in premises)
    div_prem   = '<div style="color:#495057;margin-bottom:2px">'+prem_html+'</div>'
    div_bar    = '<div style="color:#adb5bd;letter-spacing:1px">'+bar+'<span style="color:#0d6efd;font-size:.7rem;margin-left:6px">'+rule_label+'</span></div>'
    div_conc   = '<div style="color:#0a58ca;font-weight:600">'+conclusion+'<span style="color:#6c757d;font-size:.7rem;font-weight:400;margin-left:8px">'+desc+'</span></div>'
    return '<div style="margin:12px 0 8px 0;' + mono + '">' + div_prem + div_bar + div_conc + '</div>'



def render_tree(expl):
    """Render Souffle ADT proof tree as Datalog horizontal-rule proof notation."""
    if not expl: return
    tree  = parse_tree(expl)
    lines = _tree_to_proof_lines(tree)
    blocks = []
    rule_n = 1
    for prems, conc, desc in lines:
        blocks.append(_render_proof_block(prems, conc, desc, rule_n if prems else None))
        if prems: rule_n += 1
    proof_html = "".join(blocks)
    if lines:
        fc, fd = lines[-1][1], lines[-1][2]
        verdict_html = (
            '<div style="margin-top:12px;padding:8px 12px;background:#d1e7dd;'
            'border-radius:4px;font-family:IBM Plex Mono,monospace;font-size:.8rem">'
            '<strong>'+chr(10003)+' PERMITTED</strong> under '+fc+
            '<span style="color:#0a3622;font-size:.72rem;margin-left:8px">'+fd+'</span></div>'
        )
    else:
        verdict_html = ""
    header = (
        '<div style="font-family:IBM Plex Mono,monospace;font-size:.7rem;color:#6c757d;'
        'text-transform:uppercase;letter-spacing:.4px;margin-bottom:12px">'
        'Formal proof — Datalog derivation</div>'
    )
    st.markdown(
        '<div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:6px;'
        'padding:14px 16px;margin:8px 0">' + header + proof_html + verdict_html + '</div>',
        unsafe_allow_html=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def vclass(v):
    if v in ("ALLOWED","PERMITTED"):    return "allowed"
    if v in ("DENIED","NOT PERMITTED"): return "denied"
    if v == "ERROR":                    return "error"
    if v == "RUNNING":                  return "running"
    return "pending"

def vlabel(v):
    icons = {"ALLOWED":"✅","PERMITTED":"✅","DENIED":"❌","NOT PERMITTED":"❌",
             "ERROR":"⚠️","UNKNOWN":"❓","DEPENDS":"⚠️","RUNNING":"⏳"}
    label = "PERMITTED" if v in ("ALLOWED","PERMITTED") else \
            "DENIED"    if v in ("DENIED","NOT PERMITTED") else v
    return f"{icons.get(v,'❓')} {label}"

def norm_v(v):
    if v in ("ALLOWED","PERMITTED"):    return "PERMITTED"
    if v in ("DENIED","NOT PERMITTED"): return "DENIED"
    return v

def pills(cits):
    if not cits: return '<span style="color:#adb5bd;font-size:.8rem">—</span>'
    def _fmt(c):
        # Art.X citations already contain their own prefix; others get §
        if c.startswith("Art") or c.startswith("§") or c.startswith("§"):
            return f'<span class="pill">{c}</span>'
        return f'<span class="pill">§{c}</span>'
    return "".join(_fmt(c) for c in cits)

def infer_denied_cits(scenario, regulation=None):
    """Return fallback citations when the engine produced no citations for a DENIED verdict.
    Only applied when citations are genuinely empty — never overrides extracted citations."""
    reg = regulation or get_settings().get("active_regulation", "hipaa")
    # Non-HIPAA regulations: return empty rather than injecting wrong section numbers
    if reg == "gdpr":   return []
    if reg == "ccpa":   return []
    if reg == "coppa":  return []
    if reg == "glba":   return []
    if reg == "sox":    return []
    # HIPAA: infer from scenario attributes
    t = getattr(scenario, "attribute", "")
    u = getattr(scenario, "purpose", "")
    if u == "marketing":           return ["164.508", "164.508(a)(3)"]
    if t == "psychotherapy-notes": return ["164.508", "164.508(a)(2)"]
    if u == "research":            return ["164.508", "164.512(i)"]
    return ["164.502"]

def card_html(title, result=None, running=False):
    if running:
        return (f'<div class="rc running"><div class="ct">{title}</div>'
                f'<div class="va running">⏳ Running…</div></div>')
    if result is None:
        return (f'<div class="rc pending"><div class="ct">{title}</div>'
                f'<div style="color:#adb5bd">Not selected</div></div>')
    v   = getattr(result,"verdict","UNKNOWN")
    css = vclass(v)
    lat = getattr(result,"latency_seconds",0)
    cit = getattr(result,"citations",[])
    if not cit and norm_v(v)=="DENIED":
        cit = infer_denied_cits(getattr(result,"scenario",result), get_settings().get("active_regulation","hipaa"))
    return (f'<div class="rc {css}"><div class="ct">{title}</div>'
            f'<div class="va {css}">{vlabel(v)}</div>'
            f'<div style="margin-top:5px">{pills(cit)}</div>'
            f'<div style="color:#6c757d;font-size:.72rem;margin-top:4px">⏱ {lat}s</div></div>')


# ─────────────────────────────────────────────────────────────────────────────
# Strategy runners (cached per session)
# ─────────────────────────────────────────────────────────────────────────────

def _rag_cached():
    """Return a RAGStrategy cached in session state, keyed by regulation."""
    cur_reg   = get_settings().get("active_regulation", "hipaa")
    cache_key = f"rag_instance_{cur_reg}"
    if st.session_state.get(cache_key) is None:
        from strategies.rag import RAGStrategy
        r = RAGStrategy()
        with st.spinner(f"Building RAG index for {cur_reg.upper()}…"):
            try: r.build_index()
            except Exception as e: st.warning(f"RAG index ({cur_reg}): {e}")
        st.session_state[cache_key] = r
    return st.session_state[cache_key]


def run_strategy(key: str, question: str, progress_callback=None):
    try:
        from regulation_router import RegulationRouter
        # Inject Streamlit session state so RAG cache is preserved across calls
        if key == "rag":
            return _rag_cached().run(question)
        return RegulationRouter(session_state=st.session_state).run(
            key, question, progress_callback=progress_callback
        )
    except Exception as e:
        from strategies.baseline import BaselineResult
        return BaselineResult(question=question, verdict="ERROR", error=str(e))


def render_formal(res):
    v   = getattr(res,"verdict","UNKNOWN")
    cit = getattr(res,"citations",[])
    if not cit and norm_v(v)=="DENIED":
        cit = infer_denied_cits(getattr(res,"scenario",res), get_settings().get("active_regulation","hipaa"))
    if getattr(res,"answer",""):
        st.markdown(res.answer)
    if cit:
        st.markdown(pills(cit), unsafe_allow_html=True)

    # ── Proof tree ─────────────────────────────────────────────────────────
    if getattr(res,"explanation_tree",""):
        render_tree(res.explanation_tree)
    elif norm_v(v)=="DENIED":
        st.markdown(
            '<div style="background:#fff5f5;border:1px solid #f5c2c7;border-radius:6px;'
            'padding:10px 14px;font-size:.85rem;color:#842029;margin:8px 0">'
            '❌ <strong>Soufflé: no permitting rule found.</strong><br/>'
            '<span style="font-size:.82rem;color:#6c757d;margin-top:4px;display:block">'
            'HIPAA rules are encoded as a <em>whitelist</em> — only permitted disclosures '
            'have explicit rules in the Soufflé engine. The engine searched every applicable '
            'rule (§164.502, §164.506, §164.512, etc.) and none fired for this '
            'sender / receiver / purpose combination. Under the <em>closed-world assumption</em>, '
            'anything not explicitly permitted is denied by default — there is no separate '
            '"prohibited" list; absence of permission is itself the denial.'
            '</span></div>',
            unsafe_allow_html=True)

    st.caption(f"⏱ {getattr(res,'latency_seconds',0)}s  ·  "
               f"provider:{getattr(res,'provider','?')}/{getattr(res,'model','?')}"
               + (f"  ·  📁 {Path(res.run_dir).name}" if getattr(res,'run_dir','') else ""))

    if getattr(res,"error","") and v=="ERROR":
        st.error(res.error)

    # ── Souffle precedence graph ───────────────────────────────────────────────
    graph_attr = getattr(res, "precedence_graph_dot", "")
    if graph_attr:
        with st.expander("📊 Rule dependency graph (Soufflé precedence)", expanded=False):
            st.caption("Static view of HIPAA rule dependencies — same for all queries. "
                       "Shows how Soufflé stratifies the ruleset.")
            st.markdown(graph_attr, unsafe_allow_html=True)

    # ── Souffle explain — proof tree ───────────────────────────────────────────
    explain_out = getattr(res, "explain_output", "")
    v = getattr(res, "verdict", "UNKNOWN")
    if explain_out:
        if norm_v(v) == "DENIED":
            tree_label = "🌳 Denial derivation — Soufflé proof via is_disclosure_denied"
            tree_caption = ("Soufflé derivation proof: shows how is_disclosure_denied was derived "
                            "(disclosure was attempted AND no permitting rule matched).")
        else:
            tree_label = "🌳 Proof tree — why this disclosure IS permitted"
            tree_caption = ("Soufflé derivation proof tree: shows exactly which rules fired "
                            "to produce the PERMITTED verdict.")
        with st.expander(tree_label, expanded=False):
            st.caption(tree_caption)
            st.code(explain_out, language=None)

    # ── Full formal engine trace (debug expander) ───────────────────────────
    with st.expander("🔍 Formal engine trace", expanded=False):
        sc = getattr(res,"scenario",None)
        if sc:
            st.markdown("**① LLM1 extracted scenario (input to Souffle):**")
            rows_data = [
                ("sender",        f"`{sc.sender}` role=`{sc.sender_role}`"),
                ("receiver",      f"`{sc.receiver}` role=`{sc.receiver_role}`"),
                ("subject",       f"`{sc.subject}` cat=`{sc.subject_category}`"),
                ("attribute",     f"`{sc.attribute}`"),
                ("purpose",       f"`{sc.purpose}`"),
                ("same_org",      str(sc.same_org)),
                ("is_BA",         str(sc.is_business_associate)),
                ("reply_to_req",  str(sc.is_reply_to_request)),
                ("provider_pt",   str(sc.provider_patient)),
                ("authorization", str(sc.obtained_authorization_164_508)),
            ]
            for k,val in rows_data:
                st.markdown(f"- **{k}**: {val}")
            if getattr(sc,"extra_facts",[]):
                st.markdown("- **extra_facts**: " + str(sc.extra_facts))

        if getattr(res,"generated_facts",""):
            st.markdown("**② Generated Datalog facts file:**")
            st.code(res.generated_facts, language="prolog")

        rd = getattr(res,"run_dir","")
        if rd and os.path.isdir(rd):
            out = os.path.join(rd,"output")
            if os.path.isdir(out):
                st.markdown("**③ Souffle output CSVs:**")
                for f in sorted(os.listdir(out)):
                    sz = os.path.getsize(os.path.join(out,f))
                    note = " ← **verdict here**" if "allowed" in f or "denied" in f else ""
                    st.markdown(f"`{f}` — {sz:,} bytes{note}")
                # Show allowed/denied content inline if small
                for csv_name in ("is_disclosure_allowed.csv","is_disclosure_denied.csv"):
                    csv_path = os.path.join(out,csv_name)
                    if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
                        st.markdown(f"**{csv_name}:**")
                        st.code(open(csv_path).read()[:800], language=None)
            log = os.path.join(rd,"souffle.log")
            if os.path.exists(log):
                log_txt = open(log).read().strip()
                if log_txt:
                    st.markdown("**④ Souffle log:**")
                    st.code(log_txt[:1500], language=None)



def render_cmp(results: dict):
    active = [(STRAT_LABELS.get(k,k), r) for k,r in results.items() if r is not None]
    if not active: return
    from collections import Counter
    norms   = [norm_v(getattr(r,"verdict","UNKNOWN")) for _,r in active]
    counts  = Counter(norms)
    top2    = counts.most_common(2)
    # Tie-break: if PERMITTED and DENIED are tied, conservative default is DENIED
    if len(top2) >= 2 and top2[0][1] == top2[1][1]:
        majority = "DENIED"   # tie → conservative
        is_tie   = True
    else:
        majority = top2[0][0]
        is_tie   = len(set(norms)) > 1

    rows = ""
    for name, r in active:
        v   = getattr(r,"verdict","UNKNOWN")
        nv  = norm_v(v)
        lat = getattr(r,"latency_seconds","—")
        cit = getattr(r,"citations",[])
        if not cit and nv=="DENIED": cit = infer_denied_cits(getattr(r,"scenario",r), get_settings().get("active_regulation","hipaa"))
        cit_s = ", ".join(c if c.startswith("Art") else f"§{c}" for c in cit) if cit else "—"
        cc  = "ca" if nv=="PERMITTED" else "cd" if nv=="DENIED" else "ce"
        ag  = '<span class="ag-y">✓</span>' if nv==majority else '<span class="ag-n">✗</span>'
        rows += (f"<tr><td><strong>{name}</strong></td>"
                 f'<td><span class="{cc}">{vlabel(v)}</span></td>'
                 f'<td style="font-family:IBM Plex Mono,monospace;font-size:.74rem">{cit_s}</td>'
                 f"<td>{lat}s</td><td style='text-align:center'>{ag}</td></tr>")

    if is_tie and counts.get("PERMITTED",0) == counts.get("DENIED",0):
        note  = " &nbsp;🔴 <em>Tied — defaulting to DENIED (conservative)</em>"
    elif is_tie:
        note  = " &nbsp;⚠️ <em>Strategies disagree</em>"
    else:
        note  = ""
    mc = "ca" if majority=="PERMITTED" else "cd" if majority=="DENIED" else ""
    st.markdown(f"""
    <table class="cmp"><thead><tr>
      <th>Strategy</th><th>Verdict</th><th>Citations</th><th>Latency</th><th>Agrees</th>
    </tr></thead><tbody>{rows}</tbody></table>
    <div style="margin-top:10px;padding:8px 14px;border-radius:6px;background:#f8f9fa;
                border:1px solid #dee2e6;font-size:.85rem">
      <strong>Majority verdict:</strong> <span class="{mc}">{majority}</span>{note}
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar navigation
# ─────────────────────────────────────────────────────────────────────────────

s = get_settings()

with st.sidebar:
    st.markdown("## ⚖️ ComplianceGPT")
    st.divider()

    page = st.radio(
        "Navigate",
        ["Compliance Checker", "Methodology & Approaches", "Batch Evaluation", "⚙️ Settings"],
        key="page_selector",
        label_visibility="collapsed",
    )
    st.session_state["page"] = page
    st.divider()

    # Only show operational controls on the checker page
    if page == "Compliance Checker":
        st.divider()

        # Mode
        st.markdown("**Mode**")
        mode = st.radio("mode", ["Single Question","Chat"], horizontal=True,
                        label_visibility="collapsed",
                        index=0 if st.session_state["mode"]=="single" else 1)
        st.session_state["mode"] = "single" if mode=="Single Question" else "chat"
        st.divider()

        # Strategies
        st.markdown("**Strategies**")
        cur_strats = s["active_strategies"] if isinstance(s["active_strategies"],list) else ["formal"]
        new_strats = []
        for sk in ["baseline","rag","formal","agentic"]:
            disabled = False  # all regulations support all strategies
            val = st.checkbox(STRAT_LABELS[sk], value=sk in cur_strats and not disabled,
                              key=f"sb_strat_{sk}", disabled=disabled)
            if val and not disabled: new_strats.append(sk)
        if set(new_strats) != set(cur_strats):
            s["active_strategies"] = new_strats; s.save()
        st.divider()

        # Model info
        st.markdown("**Active Models**")
        p1,m1 = s.effective_llm1_model()
        p2,m2 = s.effective_llm2_model()
        st.markdown(f"`LLM1` {p1}/{m1[:20]}")
        st.markdown(f"`LLM2` {p2}/{m2[:20]}")
        if st.button("⚙️ Go to Settings", use_container_width=True, key="goto_settings"):
            st.session_state["page"] = "⚙️ Settings"
            st.rerun()
        st.divider()

        # Examples
        st.markdown("**Examples**")
        for ex in EXAMPLES.get(s["active_regulation"], EXAMPLES["hipaa"]):
            short = (ex[:44]+"…") if len(ex)>44 else ex
            if st.button(short, key=f"ex_{hash(ex)}", use_container_width=True):
                # Set the appropriate text_area widget state directly so it always
                # overrides any previously typed value.  Using value= only sets the
                # default and is ignored once the widget already has session state.
                if st.session_state.get("mode") == "chat":
                    st.session_state["chat_area"] = ex
                else:
                    st.session_state["question_input"] = ex
                st.rerun()
        st.divider()

        if st.session_state["history"]:
            st.markdown("**Recent**")
            for h in reversed(st.session_state["history"][-4:]):
                v = h.get("verdict","?")
                icon = "✅" if norm_v(v)=="PERMITTED" else "❌" if norm_v(v)=="DENIED" else "❓"
                st.markdown(f"{icon} {h['question'][:40]}…")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Compliance Checker
# ─────────────────────────────────────────────────────────────────────────────

if page == "Compliance Checker":
    reg_label   = REGULATIONS.get(s["active_regulation"], s["active_regulation"])
    active_strats = [x for x in (s["active_strategies"] or ["formal"])]
    strat_display = " · ".join(STRAT_LABELS.get(x,x) for x in active_strats)

    col_h1, col_h2 = st.columns([3,2])
    with col_h1:
        st.markdown(f"# ComplianceGPT")
        st.markdown(f"Regulatory compliance checker — **{reg_label}**")
    with col_h2:
        st.markdown(
            f'<div style="text-align:right;padding-top:20px">'
            f'<span style="background:#fff3cd;border:1px solid #ffc107;border-radius:20px;'
            f'padding:3px 12px;font-family:IBM Plex Mono,monospace;font-size:.75rem;color:#664d03">'
            f'{reg_label}</span><br>'
            f'<span style="font-family:IBM Plex Mono,monospace;font-size:.7rem;color:#6c757d">'
            f'T=0.0  ·  LLM1:{s["llm1_model"][:18]}  ·  LLM2:{s["llm2_model"][:18]}</span></div>',
            unsafe_allow_html=True)

    if not active_strats:
        st.warning("Select at least one strategy in the sidebar.")
    st.divider()

    # ── Single Question ───────────────────────────────────────────────────────
    if st.session_state["mode"] == "single":
        # ── Regulation selector ───────────────────────────────────────────────
        reg_keys_all = list(REGULATIONS.keys())
        cur_reg_now  = s["active_regulation"] if s["active_regulation"] in reg_keys_all else "hipaa"
        sel_reg = st.selectbox(
            "📋 Checking under regulation:",
            reg_keys_all,
            format_func=lambda k: REGULATIONS[k],
            index=reg_keys_all.index(cur_reg_now),
            key="main_reg_sel",
        )
        if sel_reg != s["active_regulation"]:
            s["active_regulation"] = sel_reg; s.save()
            st.rerun()
        st.divider()

        question = st.text_area("q", key="question_input",
                                placeholder=f"Ask a {REGULATIONS.get(s['active_regulation'], reg_label)} question…",
                                height=72, label_visibility="collapsed")
        col_info, col_run = st.columns([3,1])
        with col_info:
            st.markdown(f'<span style="font-size:.82rem;color:#6c757d">Running: '
                        f'<strong>{strat_display}</strong></span>', unsafe_allow_html=True)
        with col_run:
            go = st.button("▶  Check", use_container_width=True, disabled=not active_strats)
        st.divider()

        if go and question.strip():
            q = question.strip()
            results = {}
            cur_active_reg = s["active_regulation"]

            # ── Status cards (one per strategy, visible on main page) ──────────
            oc = st.columns(max(len(active_strats), 1))
            card_phs = [oc[i].empty() for i in range(len(active_strats))]
            for i, strat in enumerate(active_strats):
                card_phs[i].markdown(card_html(STRAT_LABELS[strat], running=True), unsafe_allow_html=True)
            st.divider()

            # Single progress placeholder on main page — Formal/Agentic step
            # feedback shows here, not buried inside a tab the user may not be on.
            progress_ph = st.empty()

            # Run all strategies outside any tab context so card updates and
            # progress messages are visible on the main page immediately.
            for i, strat in enumerate(active_strats):
                if strat in ("formal", "agentic"):
                    def _cb(msg, _ph=progress_ph, _lbl=STRAT_LABELS[strat]):
                        _ph.info(f"**{_lbl}** — ⠿ {msg}")
                    res = run_strategy(strat, q, progress_callback=_cb)
                    progress_ph.empty()
                else:
                    with st.spinner(f"{STRAT_LABELS[strat]}…"):
                        res = run_strategy(strat, q)
                results[strat] = res
                # Update this strategy's card immediately after it finishes
                card_phs[i].markdown(card_html(STRAT_LABELS[strat], res), unsafe_allow_html=True)

            progress_ph.empty()
            st.divider()

            # Detailed output in tabs — shown after all strategies complete.
            if active_strats:
                tabs = st.tabs([STRAT_LABELS[s2] for s2 in active_strats])
                for i, strat in enumerate(active_strats):
                    with tabs[i]:
                        res = results[strat]
                        if strat in ("formal", "agentic") and cur_active_reg != "hipaa":
                            st.info(
                                f"ℹ️ The Formal/Agentic engines use a generic bridge interface for "
                                f"**{REGULATIONS.get(cur_active_reg, cur_active_reg.upper())}**. "
                                f"LLM1 extracts scenario facts, the Soufflé engine evaluates them under "
                                f"{cur_active_reg.upper()} rules, and LLM2 explains the result using "
                                f"{cur_active_reg.upper()} citations only. For best coverage on "
                                f"{cur_active_reg.upper()} questions, **RAG** retrieves actual regulatory "
                                f"text and tends to be most accurate.",
                                icon=None,
                            )
                        if strat == "formal":
                            render_formal(res)
                        else:
                            if getattr(res, "answer", ""): st.markdown(res.answer)
                            cit = getattr(res, "citations", [])
                            if not cit and norm_v(getattr(res, "verdict", "")) == "DENIED":
                                cit = infer_denied_cits(getattr(res, "scenario", res), cur_active_reg)
                            if cit: st.markdown(pills(cit), unsafe_allow_html=True)
                            prov = getattr(res, "provider", "?"); mod = getattr(res, "model", "?")
                            st.caption(f"⏱ {getattr(res, 'latency_seconds', 0)}s  ·  {prov}/{mod}  ·  T=0.0")
                            if strat == "rag" and getattr(res, "retrieved_docs", []):
                                with st.expander("Retrieved documents"):
                                    for d in res.retrieved_docs:
                                        st.markdown(f"`{d['source']}` §{d['section']} score:{d['score']}")
                            if strat == "agentic":
                                if getattr(res, "retry_count", 0): st.info(f"Agent D self-corrected {res.retry_count}×")
                                if getattr(res, "explanation_tree", ""):
                                    render_tree(res.explanation_tree)
                                with st.expander("🔍 Agentic engine trace", expanded=False):
                                    sc2 = getattr(res, "scenario", None)
                                    if sc2:
                                        st.markdown("**Final validated scenario:**")
                                        for kk, vv in [("sender", f"`{sc2.sender}` ({sc2.sender_role})"),
                                                       ("receiver", f"`{sc2.receiver}` ({sc2.receiver_role})"),
                                                       ("attribute", f"`{sc2.attribute}`"),
                                                       ("purpose", f"`{sc2.purpose}`"),
                                                       ("reply_to_request", str(sc2.is_reply_to_request)),
                                                       ("same_org", str(sc2.same_org))]:
                                            st.markdown(f"- **{kk}**: {vv}")
                                    if getattr(res, "generated_facts", ""):
                                        st.markdown("**Datalog facts:**")
                                        st.code(res.generated_facts, language="prolog")
                                    rd3 = getattr(res, "run_dir", "")
                                    if rd3 and os.path.isdir(rd3):
                                        out3 = os.path.join(rd3, "output")
                                        if os.path.isdir(out3):
                                            for cn in ("is_disclosure_allowed.csv", "is_disclosure_denied.csv"):
                                                cp = os.path.join(out3, cn)
                                                if os.path.exists(cp) and os.path.getsize(cp) > 0:
                                                    st.markdown(f"**{cn}:**")
                                                    st.code(open(cp).read()[:600], language=None)
                                    if getattr(res, "traces", []):
                                        st.markdown("**Agent call log:**")
                                        for t in res.traces:
                                            c = "#198754" if t.success else "#dc3545"
                                            st.markdown(
                                                f'<span style="color:{c};font-weight:700">{"✓" if t.success else "✗"}</span> '
                                                f'**{t.agent}** `{t.latency}s`' + (f" — {t.notes}" if t.notes else ""),
                                                unsafe_allow_html=True)
                            if getattr(res, "error", "") and getattr(res, "verdict", "") == "ERROR":
                                st.error(res.error)
                            st.caption(f"⏱ {getattr(res, 'latency_seconds', 0)}s")

            if len(results) > 1:
                st.divider()
                st.markdown("### 📊 Strategy Comparison")
                render_cmp(results)

            best_v = next((getattr(r, "verdict", "") for r in results.values()), "")
            st.session_state["history"].append({"question": q, "verdict": best_v})

        elif go:
            st.warning("Please enter a question.")
        else:
            st.markdown("""
            <div style="border:1px solid #dee2e6;border-radius:10px;padding:40px;
                        text-align:center;background:#f8f9fa;margin-top:20px">
                <div style="font-size:2.5rem">⚖️</div>
                <h3 style="color:#1a1a2e;margin:16px 0 8px">Enter a question above</h3>
                <p style="color:#6c757d;max-width:480px;margin:0 auto">
                  All LLM calls use temperature 0.0 for deterministic results.<br>
                  Configure strategies and models in the sidebar.
                </p>
            </div>""", unsafe_allow_html=True)

    # ── Chat ──────────────────────────────────────────────────────────────────
    else:
        st.markdown(f"**Chat mode** — {reg_label} · {strat_display}")
        st.divider()
        for msg in st.session_state["chat_messages"]:
            if msg["role"]=="user":
                st.markdown(f'<div class="clabel">You</div><div class="cu">{msg["text"]}</div>',
                            unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="clabel">ComplianceGPT</div>'
                            f'<div class="cb">{msg["text"]}</div>', unsafe_allow_html=True)
                res = msg.get("formal_result")
                if res:
                    v=getattr(res,"verdict",""); css=vclass(v)
                    cit=getattr(res,"citations",[])
                    if not cit and norm_v(v)=="DENIED": cit=infer_denied_cits(getattr(res,"scenario",res), get_settings().get("active_regulation","hipaa"))
                    st.markdown(f'<div style="margin:4px 60px 4px 0">'
                                f'<span class="va {css}">{vlabel(v)}</span> &nbsp; {pills(cit)}</div>',
                                unsafe_allow_html=True)
                    if getattr(res,"explanation_tree",""):
                        with st.expander("Legal reasoning chain"): render_tree(res.explanation_tree)

        chat_q  = st.text_area("cq", placeholder="Ask a follow-up…",
                               height=65, label_visibility="collapsed", key="chat_area")
        cs, cc = st.columns([3,1])
        with cs: send = st.button("Send ↵", use_container_width=True, key="chat_send")
        with cc:
            if st.button("Clear", key="chat_clr", use_container_width=True):
                st.session_state["chat_messages"]=[]; st.rerun()

        if send and chat_q.strip():
            q = chat_q.strip()
            st.session_state["chat_messages"].append({"role":"user","text":q})
            prev = [m for m in st.session_state["chat_messages"][:-1]][-4:]
            ctx  = "\n".join(f"{'User' if m['role']=='user' else 'Asst'}: {m['text'][:180]}" for m in prev)
            q_ctx = f"Previous:\n{ctx}\n\nQuestion: {q}" if ctx else q
            formal_res=None; parts=[]
            with st.spinner("Checking…"):
                for strat in active_strats:
                    res=run_strategy(strat,q_ctx)
                    if strat=="formal": formal_res=res
                    ans=getattr(res,"answer","")
                    if ans: parts.append(f"**{STRAT_LABELS[strat]}:** {ans}" if len(active_strats)>1 else ans)
            bot="\n\n".join(parts) if parts else "Unable to process. Please try rephrasing."
            st.session_state["chat_messages"].append({"role":"bot","text":bot,"formal_result":formal_res})
            st.rerun()
        elif send:
            st.warning("Enter a question.")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Methodology
# ─────────────────────────────────────────────────────────────────────────────

elif page == "Methodology & Approaches":
    st.markdown("# 📖 Methodology & Approaches")
    st.markdown(
        "ComplianceGPT uses four strategies with different tradeoffs between formal "
        "guarantees, coverage, speed, and cost. This page explains each one.")
    st.divider()

    st.markdown("## System Architecture")
    st.markdown("""
    <div class="pipe">
      <div class="pb">User question</div><div class="pa">→</div>
      <div class="pb h">Extraction<br><small>LLM1 or agents</small></div><div class="pa">→</div>
      <div class="pb h">Compliance Check<br><small>Formal engine or LLM</small></div><div class="pa">→</div>
      <div class="pb g">Plain English Answer<br><small>LLM2 or direct</small></div><div class="pa">→</div>
      <div class="pb">User</div>
    </div>
    <p>All LLM calls use <strong>temperature=0.0</strong> for deterministic, reproducible results.</p>
    """, unsafe_allow_html=True)
    st.divider()

    t1,t2,t3,t4 = st.tabs(["1 · Baseline","2 · RAG","3 · Formal Souffle","4 · Agentic"])

    with t1:
        st.markdown("## Strategy 1 — Baseline LLM")
        col1,col2 = st.columns([3,2])
        with col1:
            st.markdown("""
**What:** Sends the question directly to an LLM with a regulation-aware system prompt. No retrieval, no formal engine.

**Pipeline:**
            """)
            st.markdown('<div class="pipe"><div class="pb">Question</div><div class="pa">→</div><div class="pb h">LLM + system prompt</div><div class="pa">→</div><div class="pb g">Answer</div></div>', unsafe_allow_html=True)
            st.markdown("""
**Why included:** Serves as the lower bound. If a more complex strategy can't outperform a vanilla LLM call, the added complexity isn't justified. Also useful for questions outside the formal engine's coverage.

**Temperature:** `0.0` — ensures deterministic output across runs.

**Limitations:** No formal guarantees. The same question rephrased may yield different answers. May hallucinate section numbers. Reasoning draws from training data, not the regulatory text itself. No audit trail.
            """)
        with col2:
            st.markdown("""
<div class="callout pro">✓ Handles any question including edge cases<br>✓ Fast (1 API call)<br>✓ Good with nuance and context<br>✓ No Souffle required</div>
<div class="callout con">✗ No formal guarantees<br>✗ Can hallucinate citations<br>✗ No audit trail<br>✗ Cannot be used for legal defense</div>
<div class="callout note">⚠ Use as baseline comparison, or for questions outside the formalized sections</div>
            """, unsafe_allow_html=True)

    with t2:
        st.markdown("## Strategy 2 — Retrieval-Augmented Generation (RAG)")
        col1,col2 = st.columns([3,2])
        with col1:
            st.markdown("""
**What:** Retrieves the most relevant CFR sections from the actual regulatory text and provides them as context. The LLM reasons only over that retrieved text, not training data.

**Pipeline:**
            """)
            st.markdown('<div class="pipe"><div class="pb">Question</div><div class="pa">→</div><div class="pb h">Hybrid retrieval<br><small>BM25 + Semantic</small></div><div class="pa">→</div><div class="pb h">Top-k CFR chunks</div><div class="pa">→</div><div class="pb h">LLM (grounded)</div><div class="pa">→</div><div class="pb g">Answer</div></div>', unsafe_allow_html=True)
            st.markdown("""
**Hybrid retrieval (Algorithm 2):**
- **BM25 (lexical):** keyword overlap — catches exact statutory terms like "psychotherapy notes", "§164.508"
- **Semantic (dense):** cosine similarity between embeddings — catches paraphrased queries
- **Combined score:** `α · semantic + (1-α) · BM25`  (α=0.5 default, configurable)

**Knowledge base:** eCFR Title 45 XML parsed into per-section `.txt` files. Run `python scripts/parse_ecfr_xml.py --api --out data/ecfr_parsed` to build.

**Why this matters:** Legal language is highly specific. A pure semantic search might confuse "psychotherapy notes" with "medical records." BM25 catches exact terms; semantic search handles paraphrasing. Legal compliance needs both.

**Temperature:** `0.0`
            """)
        with col2:
            st.markdown("""
<div class="callout pro">✓ Grounded in actual regulatory text<br>✓ Handles updates — re-index new text<br>✓ Works for unformalized sections<br>✓ Cites real section numbers</div>
<div class="callout con">✗ LLM reasoning step can misinterpret retrieved text<br>✗ Wrong retrieval → wrong answer<br>✗ Index build time on first run</div>
<div class="callout note">⚠ Best for questions about §164.520, §164.522, §164.528, §164.530 — sections not yet in Souffle</div>
            """, unsafe_allow_html=True)

    with t3:
        st.markdown("## Strategy 3 — Formal Souffle Datalog Engine")
        col1,col2 = st.columns([3,2])
        with col1:
            st.markdown("""
**What:** Translates the question into formal logical facts, runs them through a symbolic engine encoding HIPAA as Datalog rules, and produces a verdict with a machine-checkable proof tree.

**Pipeline:**
            """)
            st.markdown('<div class="pipe"><div class="pb">Question</div><div class="pa">→</div><div class="pb h">LLM1: Extractor<br><small>NL → Datalog</small></div><div class="pa">→</div><div class="pb g">Souffle Engine<br><small>Symbolic rules</small></div><div class="pa">→</div><div class="pb h">LLM2: Explainer<br><small>ADT → English</small></div><div class="pa">→</div><div class="pb g">Answer + proof</div></div>', unsafe_allow_html=True)
            st.markdown("""
**Why Souffle Datalog:** Unlike Prolog, Datalog always terminates, has no function symbols, and evaluates in polynomial time. HIPAA's conditional structure maps naturally: *"if covered entity AND treatment purpose AND provider receiver → ALLOWED"* is a single Datalog rule.

**The explanation tree** is the key differentiator — every ALLOWED verdict comes with a machine-readable proof showing exactly which rules fired, traceable to specific CFR paragraphs.

**Closed-world assumption:** If no rule permits it, it is DENIED. Conservative but legally appropriate — absence of a permitting rule means the disclosure is not authorized.

**Formalized:** §164.502, 506, 508, 510, 512, 514, 524  
**Stubs (conservative denial):** §164.520, 522, 528, 530

**Temperature:** LLM1 and LLM2 both use `0.0`. Souffle itself is deterministic.
            """)
        with col2:
            st.markdown("""
<div class="callout pro">✓ Formal guarantees — if ALLOWED, a proof exists<br>✓ Fully deterministic and reproducible<br>✓ Machine-checkable audit trail<br>✓ Persistent run artifacts for every query<br>✓ No LLM in the compliance reasoning step</div>
<div class="callout con">✗ Coverage limited to formalized sections<br>✗ LLM1 extraction errors propagate<br>✗ Requires Souffle installed locally<br>✗ UNKNOWN if LLM1 uses wrong string constants</div>
<div class="callout key">🔑 Primary strategy for production use. The formal proof is what makes it legally defensible.</div>
            """, unsafe_allow_html=True)

    with t4:
        st.markdown("## Strategy 4 — Agentic Multi-Step Pipeline")
        col1,col2 = st.columns([3,2])
        with col1:
            st.markdown("""
**What:** Decomposes the compliance check into specialized agent calls. Adds self-correction when Souffle returns UNKNOWN.

**Pipeline:**
            """)
            st.markdown('<div class="pipe"><div class="pb h">A: Extract</div><div class="pa">→</div><div class="pb h">B: Map sections</div><div class="pa">→</div><div class="pb h">C: Validate</div><div class="pa">→</div><div class="pb g">Souffle</div><div class="pa">→</div><div class="pb h">D: Fix (if needed)</div><div class="pa">→</div><div class="pb h">E: Explain</div></div>', unsafe_allow_html=True)

            st.markdown("""
| Agent | Role |
|-------|------|
| **A — Extractor** | Pulls entities: who, what type of data, to whom, why |
| **B — Mapper** | Identifies which HIPAA sections are relevant |
| **C — Validator** | Enforces valid Souffle string constants — acts as a type-checker |
| **D — Resolver** | Diagnoses UNKNOWN verdicts and produces a corrected JSON (up to 2 retries) |
| **E — Explainer** | Translates formal result to plain English |

**Why separate concerns:** Strategy 3 uses one LLM call to simultaneously parse the question, select valid roles, choose attributes, set oracle predicates, and populate extra_facts. That's a lot for one prompt. The agentic split lets each agent focus on one task with a focused prompt — and Agent C acts as a type system that catches "physician" vs "doctor" before Souffle sees it.

**Temperature:** All agent calls use `0.0`.
            """)
        with col2:
            st.markdown("""
<div class="callout pro">✓ Most robust extraction — separation of concerns<br>✓ Self-corrects on UNKNOWN verdicts<br>✓ Agent trace shows reasoning steps<br>✓ Best accuracy on ambiguous questions<br>✓ Same formal proof as Strategy 3</div>
<div class="callout con">✗ 4–6 LLM calls per question (slowest)<br>✗ Most expensive (token cost)<br>✗ More failure points<br>✗ Still limited to formalized Souffle sections</div>
<div class="callout note">⚠ Best for batch evaluation and hard questions. For interactive use, Strategy 3 offers better latency/accuracy balance.</div>
            """, unsafe_allow_html=True)

    st.divider()
    st.markdown("## Comparison Summary")
    st.markdown("""
<table class="cmp">
<thead><tr><th>Dimension</th><th>1 · Baseline</th><th>2 · RAG</th><th>3 · Formal</th><th>4 · Agentic</th></tr></thead>
<tbody>
<tr><td><strong>Verdict source</strong></td><td>LLM training data</td><td>LLM + retrieved text</td><td>Symbolic logic</td><td>Symbolic logic</td></tr>
<tr><td><strong>Formal guarantees</strong></td><td><span class="cd">✗ None</span></td><td><span class="cd">✗ None</span></td><td><span class="ca">✓ Proof tree</span></td><td><span class="ca">✓ Proof tree</span></td></tr>
<tr><td><strong>Deterministic</strong></td><td><span class="cd">✗</span> (T=0 helps)</td><td>~ Retrieval yes</td><td><span class="ca">✓ Fully</span></td><td><span class="ca">✓ Souffle step</span></td></tr>
<tr><td><strong>Temperature</strong></td><td><span class="ca">0.0</span></td><td><span class="ca">0.0</span></td><td><span class="ca">0.0 (LLM1+LLM2)</span></td><td><span class="ca">0.0 (all agents)</span></td></tr>
<tr><td><strong>Regulation coverage</strong></td><td>All 6 (training data)</td><td>All indexed sections</td><td>Formalized sections per regulation</td><td>Formalized sections per regulation</td></tr>
<tr><td><strong>Unformalized sections</strong></td><td><span class="ca">✓ Yes</span></td><td><span class="ca">✓ Yes (if indexed)</span></td><td><span class="cd">✗ DENIED</span></td><td><span class="cd">✗ DENIED</span></td></tr>
<tr><td><strong>LLM calls</strong></td><td>1</td><td>1 + retrieval</td><td>2 (LLM1+LLM2)</td><td>4–6</td></tr>
<tr><td><strong>Typical latency</strong></td><td>~5–10s</td><td>~7–15s</td><td>~10–15s</td><td>~20–40s</td></tr>
<tr><td><strong>Audit trail</strong></td><td><span class="cd">✗ None</span></td><td>Section refs only</td><td><span class="ca">✓ Proof + artifacts</span></td><td><span class="ca">✓ Proof + agent trace</span></td></tr>
<tr><td><strong>Self-correcting</strong></td><td><span class="cd">✗</span></td><td><span class="cd">✗</span></td><td><span class="cd">✗</span></td><td><span class="ca">✓ Agent D</span></td></tr>
<tr><td><strong>Best for</strong></td><td>Comparison, edge cases</td><td>Unformalized sections</td><td>Production, interactive</td><td>Batch eval, hard questions</td></tr>
</tbody></table>
    """, unsafe_allow_html=True)

    st.divider()
    st.markdown("## Why Not Just Use an LLM?")
    st.markdown("""
Healthcare compliance errors have legal consequences. "The AI said it was OK" is not a legal defense.

**Core problems with pure LLM compliance checking:**
1. **Hallucination** — LLMs cite §164.502(a)(1)(ii) for a scenario that is actually governed by §164.508(a)(3). The citation looks correct but the reasoning is wrong.
2. **Inconsistency** — Rephrasing the same question may produce a different verdict. Compliance decisions need to be reproducible.
3. **No audit trail** — Compliance requires documentation of the specific rule that permitted a disclosure.
4. **Adversarial vulnerability** — A carefully phrased question can steer an LLM to a desired verdict. A logic engine cannot be persuaded.

The core architecture principle of ComplianceGPT: **LLMs for translation, logic for reasoning.** LLMs are excellent at parsing natural language into structured facts. Souffle Datalog is excellent at applying formal rules to those facts. Neither is used for tasks better suited to the other.

> *"ComplianceGPT is a research and educational tool. It is not a substitute for legal advice. HIPAA compliance determinations in clinical or operational contexts should be reviewed by a qualified healthcare attorney or compliance officer."*
    """)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Batch Evaluation
# ─────────────────────────────────────────────────────────────────────────────

elif page == "Batch Evaluation":
    st.markdown("# 📊 Batch Evaluation")
    st.markdown("Upload a CSV of questions, run one or more strategies, download results.")
    st.divider()

    st.markdown("## Step 1 — Upload CSV")

    col_up, col_fmt = st.columns([2,1])
    with col_up:
        uploaded = st.file_uploader("Upload benchmark CSV", type=["csv"], key="batch_upload")
    with col_fmt:
        st.markdown("**Supported formats (auto-detected):**")
        st.markdown("""
- **Your QA CSV** — `question` + `answer` columns
- **PrivacyCI** — `case_content` + `norm_type` columns
- **GoldCoin** — `generate_background` + `generate_HIPAA_type` columns
- **Any CSV** — pick columns manually below
        """)

    if uploaded:
        from connector.dataset_loader import load_dataset_from_bytes, describe_dataset, detect_format
        raw_bytes = uploaded.read()

        # Auto-detect format
        import csv as _csv, io as _io
        _reader = _csv.DictReader(_io.StringIO(raw_bytes.decode("utf-8","replace")))
        _raw = list(_reader)
        if not _raw: st.error("CSV is empty."); st.stop()
        all_cols  = list(_raw[0].keys())
        fmt = detect_format(all_cols)
        st.success(f"✓ {len(_raw)} rows  ·  detected format: **{fmt}**  ·  columns: {', '.join(all_cols[:6])}{'…' if len(all_cols)>6 else ''}")

        # Column override
        with st.expander("⚙️ Column mapping (auto-detected — override if needed)"):
            from connector.dataset_loader import detect_question_col, detect_gt_col
            auto_q = detect_question_col(all_cols, fmt)
            auto_a = detect_gt_col(all_cols, fmt)
            c1, c2 = st.columns(2)
            with c1:
                q_col = st.selectbox("Question/narrative column", all_cols,
                                     index=all_cols.index(auto_q) if auto_q in all_cols else 0,
                                     key="batch_q_col")
            with c2:
                a_col = st.selectbox("Ground truth column (optional)", ["(none)"]+all_cols,
                                     index=(["(none)"]+all_cols).index(auto_a) if auto_a in all_cols else 0,
                                     key="batch_a_col")

        # Load with smart loader
        rows_obj, _, _ = load_dataset_from_bytes(
            raw_bytes,
            question_col=q_col,
            gt_col=a_col if a_col != "(none)" else None,
        )
        if not rows_obj: st.error("No rows loaded."); st.stop()
        rows = rows_obj  # alias so downstream code works
        from connector.dataset_loader import describe_dataset
        desc = describe_dataset(rows_obj)

        col_s1,col_s2,col_s3,col_s4 = st.columns(4)
        def _stat(c, n, l): c.markdown(f'<div class="stat-box"><div class="stat-num">{n}</div><div class="stat-label">{l}</div></div>', unsafe_allow_html=True)
        _stat(col_s1, desc["total"],     "Total rows")
        _stat(col_s2, desc["labeled"],   "Labeled")
        _stat(col_s3, desc["permitted"], "Permitted")
        _stat(col_s4, desc["denied"],    "Denied")

        with st.expander(f"Preview (first 5 of {len(rows_obj)})"):
            st.table([{"id":r.row_id,"question":r.question[:80]+"…" if len(r.question)>80 else r.question,
                       "ground_truth":r.ground_truth,"format":r.format}
                      for r in rows_obj[:5]])
        st.divider()

        st.markdown("## Step 2 — Configure Run")
        c1,c2,c3,c4 = st.columns(4)
        with c1:
            batch_strats = st.multiselect("Strategies", ["baseline","rag","formal","agentic"],
                                          default=[s["batch_strategy"]])
        with c2:
            batch_reg_keys = list(REGULATIONS.keys())
            cur_batch_reg  = s["active_regulation"] if s["active_regulation"] in batch_reg_keys else "hipaa"
            batch_reg = st.selectbox("Regulation", batch_reg_keys,
                                     format_func=lambda k: REGULATIONS[k],
                                     index=batch_reg_keys.index(cur_batch_reg),
                                     key="batch_reg_sel")
        with c3:
            start_row = st.number_input("Start row", 1, len(rows), 1)
            end_row   = st.number_input("End row", 1, len(rows), min(len(rows), 30))
        with c4:
            st.markdown("**Models:**")
            st.markdown(f"`LLM1` {s['llm1_model'][:20]}")
            st.markdown(f"`LLM2` {s['llm2_model'][:20]}")
            st.markdown(f"`T` = 0.0")

        to_run = rows[start_row-1 : end_row]
        st.caption(f"Will process {len(to_run)} rows × {len(batch_strats)} strategies "
                   f"= {len(to_run)*len(batch_strats)} API calls")
        st.divider()

        st.markdown("## Step 3 — Run")
        run_btn = st.button(f"▶  Run {len(to_run)}×{len(batch_strats) or 1} evaluations",
                            use_container_width=True, disabled=not batch_strats)

        def norm_gt(v):
            v = v.strip().upper()
            if v in ("YES","PERMITTED","ALLOWED","TRUE"):  return "PERMITTED"
            if v in ("NO","DENIED","NOT PERMITTED","FALSE"): return "DENIED"
            return v

        if run_btn and batch_strats:
            # Apply regulation before initialising strategies
            if s["active_regulation"] != batch_reg:
                s["active_regulation"] = batch_reg; s.save()
            if "rag" in batch_strats:
                with st.spinner("Building RAG index…"):
                    try: _rag_cached()
                    except Exception as e: st.error(f"RAG init: {e}")

            prog   = st.progress(0.0)
            status = st.empty()
            log    = st.container()
            all_out= []
            total  = len(to_run)*len(batch_strats)
            step   = 0
            totals = {st2:{"ok":0,"ev":0,"err":0} for st2 in batch_strats}

            for i, row in enumerate(to_run):
                q = row.question.strip()
                if not q: step+=len(batch_strats); continue
                gt = row.ground_truth  # already normalized by dataset_loader

                for strat in batch_strats:
                    step += 1
                    prog.progress(min(step/total,1.0))
                    status.markdown(f'`[{step}/{total}]` {strat} — `{q[:60]}…`')
                    t0 = time.time()
                    try:
                        res = run_strategy(strat, q)
                        verd = getattr(res,"verdict","ERROR")
                        nv   = norm_v(verd)
                        match = ("Y" if nv==gt else "N") if gt else ""
                        if verd not in ("ERROR","UNKNOWN"):
                            totals[strat]["ev"]+=1
                            if match=="Y": totals[strat]["ok"]+=1
                        else: totals[strat]["err"]+=1
                        cit = getattr(res,"citations",[])
                        ans = getattr(res,"answer","")[:400]
                        expl= getattr(res,"explanation_tree","")[:250]
                        err = getattr(res,"error",getattr(res,"error_message",""))[:150]
                    except Exception as e:
                        verd,nv,match,cit,ans,expl = "ERROR","ERROR","","","",""
                        err = str(e)[:150]; totals[strat]["err"]+=1

                    icon = "✓" if match=="Y" else "✗" if match=="N" else "·"
                    col_c = "#198754" if match=="Y" else "#dc3545" if match=="N" else "#6c757d"
                    with log:
                        st.markdown(
                            f'<div style="font-family:IBM Plex Mono,monospace;font-size:.78rem;'
                            f'padding:3px 0;border-bottom:1px solid #f1f3f5;color:{col_c}">'
                            f'{icon} [{strat}] row {start_row+i} — {verd} — {round(time.time()-t0,1)}s</div>',
                            unsafe_allow_html=True)
                    all_out.append({
                        **{k:v for k,v in row.raw.items() if k not in (q_col, a_col)},
                        "question":q, "ground_truth":gt, "strategy":strat,
                        "verdict":verd, "verdict_norm":nv, "match":match,
                        "citations":"; ".join(cit), "latency_s":round(time.time()-t0,1),
                        "llm_answer":ans, "explanation":expl, "error":err,
                        "timestamp":datetime.now().isoformat(),
                    })

            st.session_state["batch_results"] = all_out
            prog.progress(1.0); status.markdown("**✓ Complete**")

            if any(totals[st2]["ev"]>0 for st2 in batch_strats):
                st.markdown("### Accuracy")
                acc_cols = st.columns(len(batch_strats))
                for i,st2 in enumerate(batch_strats):
                    ev=totals[st2]["ev"]; ok=totals[st2]["ok"]
                    acc=f"{ok/ev*100:.1f}%" if ev>0 else "N/A"
                    with acc_cols[i]:
                        st.markdown(f'<div class="stat-box"><div class="stat-num">{acc}</div>'
                                    f'<div class="stat-label">{st2}<br>{ok}/{ev}</div></div>',
                                    unsafe_allow_html=True)

        results = st.session_state.get("batch_results",[])
        if results:
            st.divider()
            st.markdown("## Step 4 — Download")
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=list(results[0].keys()))
            w.writeheader(); w.writerows(results)
            fname = f"compliancegpt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            st.download_button("⬇  Download Results CSV", buf.getvalue().encode(),
                               file_name=fname, mime="text/csv", use_container_width=True)
            with st.expander(f"Preview ({min(8,len(results))} rows)"):
                st.table([{k:r.get(k,"") for k in
                           ["question","strategy","verdict","match","citations","latency_s"]}
                          for r in results[:8]])

        st.divider()
        st.markdown("**CLI equivalent:**")
        st.code("python app/cli.py --benchmark data/benchmark.csv --strategy formal --output results.csv\n"
                "python app/cli.py --benchmark data/benchmark.csv --strategy all", language="bash")
    else:
        st.info("Upload a CSV above to get started.")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Settings
# ─────────────────────────────────────────────────────────────────────────────

elif page == "⚙️ Settings":
    st.markdown("# ⚙️ Settings")
    st.markdown("Configure models, API keys, and system parameters. Click **Save** to persist.")
    st.divider()

    # ── Model selectors ───────────────────────────────────────────────────────
    st.markdown("## 🤖 Model Configuration")
    st.markdown("**LLM1** extracts scenarios. **LLM2** explains results. Both use `temperature=0.0`.")

    def _fetch_ollama_models(base_url: str) -> list[str]:
        """Fetch installed Ollama models; cache in session state for this page load."""
        cache_key = f"_ollama_models_{base_url}"
        if cache_key not in st.session_state:
            try:
                import urllib.request as _ur, json as _j
                with _ur.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=3) as r:
                    data = _j.loads(r.read())
                names = sorted(m["name"] for m in data.get("models", []))
                st.session_state[cache_key] = names
                # Also persist to settings so other parts of the app can use them
                if names != s.get("active_ollama_models", []):
                    s["active_ollama_models"] = names; s.save()
            except Exception:
                # Ollama not running or unreachable — fall back to previously saved list
                st.session_state[cache_key] = s.get("active_ollama_models", [])
        return st.session_state[cache_key]

    def model_selector(role_label, provider_key, model_key):
        providers = list(MODEL_REGISTRY.keys())
        cur_p = s[provider_key]; cur_m = s[model_key]
        c1,c2 = st.columns([1,2])
        with c1:
            p = st.selectbox(f"{role_label} provider", providers,
                             index=providers.index(cur_p) if cur_p in providers else 0,
                             key=f"sp_{provider_key}")
        with c2:
            if p == "ollama":
                # Auto-fetch installed models and show as a dropdown
                ollama_url  = s.get("ollama_base_url", "http://localhost:11434")
                installed   = _fetch_ollama_models(ollama_url)
                if installed:
                    # Pick the best default: current saved model if still installed, else first
                    default_idx = installed.index(cur_m) if cur_m in installed else 0
                    chosen = st.selectbox(
                        f"{role_label} model (installed)",
                        installed,
                        index=default_idx,
                        key=f"sm_ollama_{model_key}",
                        help="Models installed on your machine via `ollama pull`. Refresh by clicking Refresh below.",
                    )
                    c_ref, c_info = st.columns([1, 2])
                    with c_ref:
                        if st.button("↻ Refresh", key=f"ref_ollama_{model_key}", use_container_width=True):
                            cache_key = f"_ollama_models_{ollama_url}"
                            if cache_key in st.session_state:
                                del st.session_state[cache_key]
                            st.rerun()
                    with c_info:
                        st.caption(f"{len(installed)} model{'s' if len(installed)!=1 else ''} found")
                    m_out = chosen
                else:
                    # Ollama not running — show text input with helpful message
                    st.warning("Ollama not detected. Start it with `ollama serve`, then click Refresh.", icon="⚠️")
                    fallback = st.text_input(
                        f"{role_label} model",
                        value=cur_m or "llama3:latest",
                        key=f"custom_ollama_{model_key}",
                        placeholder="e.g. llama3:latest",
                    )
                    if st.button("↻ Refresh", key=f"ref_ollama_{model_key}", use_container_width=True):
                        cache_key = f"_ollama_models_{ollama_url}"
                        if cache_key in st.session_state:
                            del st.session_state[cache_key]
                        st.rerun()
                    m_out = fallback or "llama3:latest"

            elif p == "huggingface":
                ck   = "hf_custom_model"
                models = MODEL_REGISTRY.get(p, [])
                ids    = [m["id"] for m in models]
                labels = [f"{m['label']}  [{m['notes']}]" for m in models]
                cval = st.text_input(f"HuggingFace model path",
                                     value=s[ck] if cur_m not in ids else cur_m,
                                     key=f"custom_{provider_key}",
                                     placeholder="e.g. meta-llama/Llama-3.3-70B-Instruct")
                if ids:
                    sel = st.selectbox("Or preset", ["— custom —"] + labels, key=f"preset_{provider_key}")
                    if sel != "— custom —":
                        for m in models:
                            if f"{m['label']}  [{m['notes']}]" == sel: cval = m["id"]; break
                m_out = cval or (ids[0] if ids else "")

            else:
                models = MODEL_REGISTRY.get(p, [])
                ids    = [m["id"] for m in models]
                labels = [f"{m['label']}  [{m['notes']}]" for m in models]
                idx = ids.index(cur_m) if cur_m in ids else 0
                sel = st.selectbox(f"{role_label} model", labels, index=idx, key=f"sm_{model_key}")
                m_out = ids[labels.index(sel)]
        return p, m_out

    lt1,lt2 = st.tabs(["LLM1 — Extractor","LLM2 — Explainer"])
    with lt1: p1,m1 = model_selector("LLM1","llm1_provider","llm1_model")
    with lt2: p2,m2 = model_selector("LLM2","llm2_provider","llm2_model")
    st.divider()

    # ── API Keys ──────────────────────────────────────────────────────────────
    st.markdown("## 🔑 API Keys")
    st.markdown("Environment variables always take priority over saved keys.")
    cA,cB,cC,cD = st.columns(4)
    def key_field(col, label, env_var, setting_key, placeholder):
        with col:
            st.markdown(f'<div class="section-header">{label}</div>', unsafe_allow_html=True)
            if os.environ.get(env_var):
                st.markdown('<span style="color:#198754;font-weight:600">✓ Set via env</span>', unsafe_allow_html=True)
                return ""
            return st.text_input(f"{label} key", value=s[setting_key],
                                 type="password", key=f"key_{setting_key}", placeholder=placeholder)
    new_ant = key_field(cA,"Anthropic","ANTHROPIC_API_KEY","anthropic_api_key","sk-ant-...")
    new_oai = key_field(cB,"OpenAI","OPENAI_API_KEY","openai_api_key","sk-...")
    new_goo = key_field(cC,"Google","GOOGLE_API_KEY","google_api_key","AIza...")
    new_hf  = key_field(cD,"HuggingFace","HUGGINGFACE_API_KEY","huggingface_api_key","hf_...")
    st.divider()

    # ── Ollama ────────────────────────────────────────────────────────────────
    st.markdown("## 🦙 Ollama (Local Models)")
    col_ol, col_detect = st.columns([3,1])
    with col_ol:
        new_ollama_url = st.text_input("Ollama URL", value=s["ollama_base_url"],
                                       key="ollama_url_s", placeholder="http://localhost:11434")
    with col_detect:
        st.markdown(""); st.markdown("")
        if st.button("🔍 Refresh models", key="detect_ollama_s", use_container_width=True):
            # Clear the session cache so model dropdowns reload
            cache_key = f"_ollama_models_{new_ollama_url}"
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            try:
                import urllib.request as _ur, json as _j
                with _ur.urlopen(f"{new_ollama_url.rstrip('/')}/api/tags", timeout=5) as r:
                    data = _j.loads(r.read())
                found = sorted(m["name"] for m in data.get("models", []))
                st.success(f"✓ {len(found)} models: {', '.join(found[:6])}")
                s["active_ollama_models"] = found; s.save()
                st.session_state[cache_key] = found
            except Exception as e:
                st.error(f"✗ Cannot reach Ollama: {e}")
    st.divider()

    # ── Default regulation & strategies ──────────────────────────────────────
    st.markdown("## 🗂️ Default Regulation & Strategies")
    st.markdown("Defaults loaded by the Compliance Checker. Overridable per-session in the sidebar.")
    col_r, col_st = st.columns([1,2])
    with col_r:
        reg_keys = list(REGULATIONS.keys())
        cur_reg  = s["active_regulation"] if s["active_regulation"] in reg_keys else "hipaa"
        new_reg  = st.selectbox("Default regulation", reg_keys,
                                format_func=lambda k: REGULATIONS[k],
                                index=reg_keys.index(cur_reg), key="def_reg")
    with col_st:
        st.markdown("**Default strategies:**")
        cur_strats = s["active_strategies"] if isinstance(s["active_strategies"],list) else ["formal"]
        new_strats = []
        sc = st.columns(4)
        for i,(sk,sl) in enumerate(STRAT_LABELS.items()):
            with sc[i]:
                disabled = False  # all regulations support all 4 strategies
                if st.checkbox(sl, value=sk in cur_strats,
                               key=f"def_strat_{sk}", disabled=disabled):
                    new_strats.append(sk)
    st.divider()

    # ── System ────────────────────────────────────────────────────────────────
    st.markdown("## ⚙️ System")
    cs1,cs2,cs3 = st.columns(3)
    with cs1:
        st.markdown('<div class="section-header">Souffle</div>', unsafe_allow_html=True)
        new_souffle_bin = st.text_input("Souffle binary (empty=auto)", value=s["souffle_binary"],
                                        key="souffle_bin_s", placeholder="/opt/homebrew/bin/souffle")
        new_timeout     = st.number_input("Timeout (s)", 5, 300, int(s["souffle_timeout"]), key="timeout_s")
    with cs2:
        st.markdown('<div class="section-header">RAG</div>', unsafe_allow_html=True)
        new_rag_k     = st.slider("k (chunks)", 1, 20, int(s["rag_k"]), key="rag_k_s")
        new_rag_alpha = st.slider("α (semantic weight)", 0.0, 1.0, float(s["rag_alpha"]),
                                  step=0.05, key="rag_a_s")
    with cs3:
        st.markdown('<div class="section-header">Batch Eval</div>', unsafe_allow_html=True)
        new_batch_strat = st.selectbox("Default batch strategy",
                                       ["baseline","rag","formal","agentic"],
                                       index=["baseline","rag","formal","agentic"].index(s["batch_strategy"]),
                                       key="batch_s")
        new_q_col = st.text_input("Question column", value=s["batch_question_col"], key="bq_s")
        new_a_col = st.text_input("Answer column", value=s["batch_answer_col"], key="ba_s")
    st.divider()

    # ── Connection test ───────────────────────────────────────────────────────
    st.markdown("## 🔌 Connection Test")
    ct1,ct2 = st.columns(2)
    with ct1:
        if st.button("Test LLM1", use_container_width=True, key="test_llm1"):
            from connector.model_client import ModelClient
            with st.spinner(f"Testing {p1}/{m1}…"):
                ok,msg = ModelClient.test_connection(p1,m1)
            (st.success if ok else st.error)(msg)
    with ct2:
        if st.button("Test LLM2", use_container_width=True, key="test_llm2"):
            from connector.model_client import ModelClient
            with st.spinner(f"Testing {p2}/{m2}…"):
                ok,msg = ModelClient.test_connection(p2,m2)
            (st.success if ok else st.error)(msg)
    st.divider()

    # ── Save ──────────────────────────────────────────────────────────────────
    col_save, col_reset = st.columns([2,1])
    with col_save:
        if st.button("💾  Save Settings", use_container_width=True, key="save_btn"):
            s["llm1_provider"]=p1; s["llm1_model"]=m1
            s["llm2_provider"]=p2; s["llm2_model"]=m2
            if new_ant: s["anthropic_api_key"]=new_ant
            if new_oai: s["openai_api_key"]=new_oai
            if new_goo: s["google_api_key"]=new_goo
            if new_hf:  s["huggingface_api_key"]=new_hf
            s["ollama_base_url"]=new_ollama_url
            s["souffle_binary"]=new_souffle_bin
            s["souffle_timeout"]=new_timeout
            s["rag_k"]=new_rag_k; s["rag_alpha"]=new_rag_alpha
            s["batch_strategy"]=new_batch_strat
            s["batch_question_col"]=new_q_col; s["batch_answer_col"]=new_a_col
            s["active_regulation"]=new_reg
            s["active_strategies"]=new_strats if new_strats else ["formal"]
            s.save()
            st.success("✓ Settings saved. Changes take effect immediately in the Compliance Checker.")
    with col_reset:
        if st.button("↺  Reset defaults", use_container_width=True, key="reset_btn"):
            from connector.settings import SETTINGS_FILE
            SETTINGS_FILE.unlink(missing_ok=True)
            st.info("Settings reset. Reload the page.")

    with st.expander("Current configuration (JSON)"):
        display = {k: ("***" if "key" in k and v else v) for k,v in s.as_dict().items()}
        st.code(json.dumps(display, indent=2), language="json")
