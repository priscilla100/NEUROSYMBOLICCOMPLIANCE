"""
app/pages/1_Settings.py
─────────────────────────────────────────────────────────────────────────────
Settings page — pick models, set API keys, configure Souffle and RAG.
Streamlit multipage: place this in app/pages/ and run from app/streamlit_app.py
"""

import sys, os
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from connector.settings import get_settings, MODEL_REGISTRY
from connector.model_client import ModelClient

st.set_page_config(page_title="Settings — ComplianceGPT", page_icon="⚙️", layout="wide")

# ── Minimal CSS (white, consistent with main app) ─────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background: #ffffff !important; }
[data-testid="stSidebar"] { background: #f8f9fa !important; border-right: 1px solid #dee2e6; }
h1, h2, h3 { color: #1a1a2e; }
p, li, label { color: #212529; }
[data-testid="stMarkdownContainer"] p { color: #212529; }
.stButton > button { background: #0d6efd !important; color: #fff !important;
    border: none !important; border-radius: 6px !important;
    font-family: 'IBM Plex Mono', monospace !important; font-weight: 600 !important; }
.stButton > button:hover { background: #0b5ed7 !important; }
hr { border-color: #dee2e6 !important; }
.status-ok  { color: #198754; font-weight: 600; font-family: 'IBM Plex Mono', monospace; }
.status-err { color: #dc3545; font-weight: 600; font-family: 'IBM Plex Mono', monospace; }
.section-header { font-family: 'IBM Plex Mono', monospace; font-size: 0.75rem;
    font-weight: 600; color: #6c757d; text-transform: uppercase;
    letter-spacing: 0.5px; margin-top: 20px; margin-bottom: 6px; }
</style>
""", unsafe_allow_html=True)

s = get_settings()

st.markdown("# ⚙️ Settings")
st.markdown("Configure models, API keys, and system parameters. Changes are saved automatically.")
st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Helper to build provider + model selector
# ─────────────────────────────────────────────────────────────────────────────

def provider_model_selector(label: str, provider_key: str, model_key: str):
    """Renders provider + model dropdowns for LLM1 or LLM2."""
    providers = list(MODEL_REGISTRY.keys())
    cur_provider = s[provider_key]
    cur_model    = s[model_key]

    col1, col2 = st.columns([1, 2])
    with col1:
        provider = st.selectbox(
            f"{label} provider",
            options=providers,
            index=providers.index(cur_provider) if cur_provider in providers else 0,
            key=f"sel_provider_{provider_key}",
        )

    with col2:
        models = MODEL_REGISTRY.get(provider, [])
        if provider in ("ollama", "huggingface"):
            # Custom input + dropdown
            custom_key = "ollama_custom_model" if provider == "ollama" else "hf_custom_model"
            custom_val = s[custom_key]
            model_ids   = [m["id"] for m in models]
            model_labels = [f"{m['label']}  [{m['notes']}]" for m in models]

            # If current model isn't in list, show as custom
            if cur_model and cur_model not in model_ids:
                display_val = cur_model
            else:
                display_val = ""

            custom_input = st.text_input(
                f"Custom {provider} model (or pick below)",
                value=display_val or custom_val,
                key=f"custom_{provider_key}",
                placeholder="e.g. llama3.2:latest" if provider == "ollama" else "org/model-name",
            )

            if model_ids:
                idx = model_ids.index(cur_model) if cur_model in model_ids else 0
                preset = st.selectbox(
                    "Or pick a preset",
                    options=["— custom —"] + model_labels,
                    index=0 if custom_input else idx + 1,
                    key=f"preset_{provider_key}",
                )
                if preset != "— custom —":
                    # Map label back to id
                    for m in models:
                        if f"{m['label']}  [{m['notes']}]" == preset:
                            chosen_model = m["id"]
                            break
                    else:
                        chosen_model = custom_input
                else:
                    chosen_model = custom_input
            else:
                chosen_model = custom_input

            s[custom_key] = chosen_model
            model = chosen_model or (model_ids[0] if model_ids else "")
        else:
            model_ids    = [m["id"]    for m in models]
            model_labels = [f"{m['label']}  [{m['notes']}]" for m in models]
            idx = model_ids.index(cur_model) if cur_model in model_ids else 0
            sel = st.selectbox(
                f"{label} model",
                options=model_labels,
                index=idx,
                key=f"sel_model_{model_key}",
            )
            model = model_ids[model_labels.index(sel)]

    return provider, model


# ─────────────────────────────────────────────────────────────────────────────
# Section 1: Model Configuration
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## 🤖 Model Configuration")
st.markdown("**LLM1** extracts structured scenarios from natural language. **LLM2** explains results in plain English.")

tab1, tab2 = st.tabs(["LLM1 — Extractor", "LLM2 — Explainer"])

with tab1:
    st.markdown('<div class="section-header">LLM1: Converts questions → Datalog facts</div>', unsafe_allow_html=True)
    p1, m1 = provider_model_selector("LLM1", "llm1_provider", "llm1_model")

with tab2:
    st.markdown('<div class="section-header">LLM2: Converts Souffle results → plain English</div>', unsafe_allow_html=True)
    p2, m2 = provider_model_selector("LLM2", "llm2_provider", "llm2_model")

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Section 2: API Keys
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## 🔑 API Keys")
st.markdown("Keys set here are saved to disk. Keys in environment variables (e.g. `ANTHROPIC_API_KEY`) always take priority.")

col_a, col_b = st.columns(2)
col_c, col_d = st.columns(2)

with col_a:
    st.markdown('<div class="section-header">Anthropic</div>', unsafe_allow_html=True)
    env_anthropic = os.environ.get("ANTHROPIC_API_KEY", "")
    if env_anthropic:
        st.markdown(f'<span class="status-ok">✓ Set via environment</span>', unsafe_allow_html=True)
        new_anthropic = ""
    else:
        saved = s["anthropic_api_key"]
        new_anthropic = st.text_input(
            "Anthropic API key", value=saved,
            type="password", key="api_anthropic",
            placeholder="sk-ant-...",
        )

with col_b:
    st.markdown('<div class="section-header">OpenAI</div>', unsafe_allow_html=True)
    env_openai = os.environ.get("OPENAI_API_KEY", "")
    if env_openai:
        st.markdown(f'<span class="status-ok">✓ Set via environment</span>', unsafe_allow_html=True)
        new_openai = ""
    else:
        new_openai = st.text_input(
            "OpenAI API key", value=s["openai_api_key"],
            type="password", key="api_openai",
            placeholder="sk-...",
        )

with col_c:
    st.markdown('<div class="section-header">Google Gemini</div>', unsafe_allow_html=True)
    env_google = os.environ.get("GOOGLE_API_KEY", "")
    if env_google:
        st.markdown(f'<span class="status-ok">✓ Set via environment</span>', unsafe_allow_html=True)
        new_google = ""
    else:
        new_google = st.text_input(
            "Google API key", value=s["google_api_key"],
            type="password", key="api_google",
            placeholder="AIza...",
        )

with col_d:
    st.markdown('<div class="section-header">HuggingFace</div>', unsafe_allow_html=True)
    env_hf = os.environ.get("HUGGINGFACE_API_KEY", "")
    if env_hf:
        st.markdown(f'<span class="status-ok">✓ Set via environment</span>', unsafe_allow_html=True)
        new_hf = ""
    else:
        new_hf = st.text_input(
            "HuggingFace API key", value=s["huggingface_api_key"],
            type="password", key="api_hf",
            placeholder="hf_...",
        )

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Section 3: Ollama Configuration
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## 🦙 Ollama (Local Models)")
col_ol1, col_ol2 = st.columns([2, 1])
with col_ol1:
    new_ollama_url = st.text_input(
        "Ollama server URL",
        value=s["ollama_base_url"],
        key="ollama_url",
        placeholder="http://localhost:11434",
    )
with col_ol2:
    st.markdown("")
    st.markdown("")
    if st.button("Test Ollama connection"):
        try:
            import urllib.request, json as _json
            url = f"{new_ollama_url.rstrip('/')}/api/tags"
            with urllib.request.urlopen(url, timeout=5) as r:
                data = _json.loads(r.read())
            models_found = [m["name"] for m in data.get("models", [])]
            if models_found:
                st.success(f"✓ Connected. Models: {', '.join(models_found[:5])}")
            else:
                st.info("✓ Connected but no models pulled yet. Run: `ollama pull llama3.2`")
        except Exception as e:
            st.error(f"✗ {e}")

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Section 4: System Configuration
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## ⚙️ System Configuration")

col_s1, col_s2, col_s3 = st.columns(3)

with col_s1:
    st.markdown('<div class="section-header">Souffle</div>', unsafe_allow_html=True)
    new_souffle_binary = st.text_input(
        "Souffle binary path (empty = auto-detect)",
        value=s["souffle_binary"],
        key="souffle_bin",
        placeholder="/opt/homebrew/bin/souffle",
    )
    new_timeout = st.number_input(
        "Souffle timeout (seconds)",
        min_value=5, max_value=300,
        value=int(s["souffle_timeout"]),
        key="souffle_timeout_input",
    )

with col_s2:
    st.markdown('<div class="section-header">RAG</div>', unsafe_allow_html=True)
    new_rag_k = st.slider("Documents to retrieve (k)", 1, 20, int(s["rag_k"]), key="rag_k_slider")
    new_rag_alpha = st.slider("Semantic weight (α)", 0.0, 1.0, float(s["rag_alpha"]),
                               step=0.05, key="rag_alpha_slider",
                               help="0 = BM25 only, 1 = semantic only, 0.5 = equal blend")

with col_s3:
    st.markdown('<div class="section-header">Batch Evaluation</div>', unsafe_allow_html=True)
    new_batch_strategy = st.selectbox(
        "Default strategy for batch eval",
        options=["baseline", "rag", "formal", "agentic"],
        index=["baseline", "rag", "formal", "agentic"].index(s["batch_strategy"]),
        key="batch_strat",
    )
    new_batch_q_col = st.text_input("Question column name", value=s["batch_question_col"], key="batch_q")
    new_batch_a_col = st.text_input("Answer column name (ground truth)", value=s["batch_answer_col"], key="batch_a")

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Section 4b: Default Regulation + Default Strategies
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## 🗂️ Default Regulation & Strategies")
st.markdown("These are the defaults loaded by the Compliance Checker page. "
            "You can override them per-session in the sidebar.")

col_r1, col_r2 = st.columns([1, 2])

REGULATIONS = {
    "hipaa": "🏥  HIPAA  — US Healthcare Privacy",
    "gdpr":  "🇪🇺  GDPR   — EU Data Protection",
    "ccpa":  "🌴  CCPA   — California Privacy",
    "glba":  "🏦  GLBA   — Financial Privacy",
    "sox":   "📊  SOX    — Financial Reporting",
    "coppa": "👶  COPPA  — Children's Online Privacy",
}

with col_r1:
    st.markdown('<div class="section-header">Default Regulation</div>', unsafe_allow_html=True)
    reg_keys = list(REGULATIONS.keys())
    cur_reg  = s["active_regulation"] if s["active_regulation"] in reg_keys else "hipaa"
    new_default_reg = st.selectbox(
        "Default regulation",
        options=reg_keys,
        format_func=lambda k: REGULATIONS[k],
        index=reg_keys.index(cur_reg),
        key="default_reg",
        label_visibility="collapsed",
    )
    if new_default_reg != "hipaa":
        st.info("Formal (Souffle) strategies only available for HIPAA currently.")

with col_r2:
    st.markdown('<div class="section-header">Default Strategies</div>', unsafe_allow_html=True)
    cur_active = s["active_strategies"] if isinstance(s["active_strategies"], list) else ["formal"]
    new_default_strats = []
    s_cols = st.columns(4)
    strat_map = {"baseline":"1 · Baseline","rag":"2 · RAG","formal":"3 · Formal","agentic":"4 · Agentic"}
    for i, (sk, sl) in enumerate(strat_map.items()):
        with s_cols[i]:
            disabled = sk in ("formal","agentic") and new_default_reg != "hipaa"
            if st.checkbox(sl, value=sk in cur_active and not disabled,
                           key=f"default_strat_{sk}", disabled=disabled):
                new_default_strats.append(sk)

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Section 4c: Ollama — detect installed models
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## 🦙 Ollama — Installed Models")

col_ol_url, col_ol_refresh = st.columns([3, 1])
with col_ol_url:
    new_ollama_url = st.text_input(
        "Ollama server URL", value=s["ollama_base_url"], key="ollama_url2",
        placeholder="http://localhost:11434",
    )
with col_ol_refresh:
    st.markdown("")
    st.markdown("")
    detect_btn = st.button("🔍 Detect models", use_container_width=True, key="detect_ollama")

ollama_models_found = []
if detect_btn or s.get("active_ollama_models"):
    try:
        import urllib.request, json as _json
        url = f"{new_ollama_url.rstrip('/')}/api/tags"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = _json.loads(r.read())
        ollama_models_found = [m["name"] for m in data.get("models", [])]
        if ollama_models_found:
            st.success(f"✓ Found {len(ollama_models_found)} models: {', '.join(ollama_models_found)}")
        else:
            st.info("Ollama connected but no models pulled. Run: `ollama pull llama3.2`")
    except Exception:
        if detect_btn:
            st.error("Cannot reach Ollama. Make sure `ollama serve` is running.")
        ollama_models_found = s.get("active_ollama_models") or []

if ollama_models_found:
    cur_ollama = s.get("active_ollama_models") or []
    selected_ollama = st.multiselect(
        "Select Ollama models to make available as LLM1/LLM2 options",
        options=ollama_models_found,
        default=[m for m in cur_ollama if m in ollama_models_found],
        key="sel_ollama_models",
    )
    if selected_ollama != cur_ollama:
        s["active_ollama_models"] = selected_ollama
        s.save()

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Section 5: Connection Test
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## 🔌 Connection Test")
st.markdown("Test your current LLM1 and LLM2 model connections.")

col_t1, col_t2 = st.columns(2)

with col_t1:
    if st.button("Test LLM1 connection", use_container_width=True):
        with st.spinner(f"Testing {p1} / {m1}…"):
            ok, msg = ModelClient.test_connection(p1, m1)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

with col_t2:
    if st.button("Test LLM2 connection", use_container_width=True):
        with st.spinner(f"Testing {p2} / {m2}…"):
            ok, msg = ModelClient.test_connection(p2, m2)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Save button
# ─────────────────────────────────────────────────────────────────────────────

col_save, col_reset = st.columns([2, 1])

with col_save:
    if st.button("💾  Save Settings", use_container_width=True, type="primary"):
        s["llm1_provider"] = p1
        s["llm1_model"]    = m1
        s["llm2_provider"] = p2
        s["llm2_model"]    = m2
        if new_anthropic: s["anthropic_api_key"] = new_anthropic
        if new_openai:    s["openai_api_key"]    = new_openai
        if new_google:    s["google_api_key"]    = new_google
        if new_hf:        s["huggingface_api_key"] = new_hf
        s["ollama_base_url"]    = new_ollama_url
        s["souffle_binary"]     = new_souffle_binary
        s["souffle_timeout"]    = new_timeout
        s["rag_k"]              = new_rag_k
        s["rag_alpha"]          = new_rag_alpha
        s["batch_strategy"]     = new_batch_strategy
        s["batch_question_col"]  = new_batch_q_col
        s["batch_answer_col"]    = new_batch_a_col
        s["active_regulation"]   = new_default_reg
        s["active_strategies"]   = new_default_strats if new_default_strats else ["formal"]
        s.save()
        st.success("✓ Settings saved! Changes take effect immediately in the Compliance Checker.")

with col_reset:
    if st.button("↺  Reset to defaults", use_container_width=True):
        from connector.settings import DEFAULTS, SETTINGS_FILE
        SETTINGS_FILE.unlink(missing_ok=True)
        st.info("Settings reset. Reload the page.")

# Current config summary
with st.expander("Current configuration summary"):
    import json
    display = {k: ("***" if "key" in k and v else v) for k, v in s.as_dict().items()}
    st.code(json.dumps(display, indent=2), language="json")
