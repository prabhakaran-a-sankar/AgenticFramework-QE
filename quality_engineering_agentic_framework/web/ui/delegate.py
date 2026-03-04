"""QE Delegate — Accenture branded agentic orchestration UI on port 8502."""
import os, requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8080")

st.set_page_config(page_title="Quality Engineering Delegate", page_icon="🤖", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
* { font-family: "Inter", "Segoe UI", Arial, sans-serif !important; }

[data-testid="stAppViewContainer"] { background: #07070f !important; }
[data-testid="stAppViewContainer"] > .main { background: #07070f !important; padding-top: 0 !important; }
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stBottom"] { background: #07070f !important; border-top: 1px solid #1e1e3a !important; }
[data-testid="stAppViewContainer"] > .main .block-container { padding-bottom: 120px !important; }
section[data-testid="stSidebar"] { display: none !important; }

.delegate-header {
    background: linear-gradient(135deg, #A100F2 0%, #6B1B9A 55%, #1a0030 100%);
    padding: 28px 40px 22px; margin: -4rem -4rem 1.5rem -4rem;
    border-bottom: 2px solid rgba(161,0,242,0.5);
}
.delegate-header h1 { color:#fff !important; font-size:2rem !important; font-weight:800 !important; margin:0 !important; }
.delegate-header p  { color:rgba(255,255,255,0.7) !important; margin:5px 0 0 !important; font-size:0.95rem !important; }
.delegate-header .badge {
    display:inline-block; background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.25);
    color:#fff; padding:2px 12px; border-radius:20px; font-size:0.75rem; margin-top:10px; letter-spacing:0.5px;
}

.cfg-panel {
    background:#0f0f1e; border:1px solid #1e1e3a; border-radius:12px;
    padding:16px 20px; margin-bottom:16px;
}

.bubble-user {
    background: linear-gradient(135deg, #A100F2, #7000b8);
    color:#fff; padding:12px 18px; border-radius:18px 18px 4px 18px;
    margin:6px 0 6px 20%; word-wrap:break-word;
    box-shadow:0 2px 14px rgba(161,0,242,0.35);
}
.bubble-bot {
    background:#111128; border:1px solid #252545;
    color:#ddddf0; padding:14px 18px; border-radius:18px 18px 18px 4px;
    margin:6px 20% 6px 0; word-wrap:break-word;
    box-shadow:0 2px 8px rgba(0,0,0,0.4);
}
.state-pill {
    display:inline-block; font-size:0.7rem; font-weight:700; padding:2px 10px;
    border-radius:12px; margin-bottom:8px; letter-spacing:0.6px; text-transform:uppercase;
}
.s-IDLE                { background:#1e1e3a; color:#7070a0; }
.s-AWAITING_REQUIREMENTS { background:#0d2a4a; color:#50a0ff; }
.s-ASSESSING           { background:#2a1e00; color:#ffaa20; }
.s-ASSESSMENT_FAILED   { background:#2a0d0d; color:#ff5555; }
.s-GENERATING          { background:#0d2a0d; color:#50cc50; }
.s-DONE                { background:#0d2a0d; color:#50cc50; }

.tc-card {
    background:#0d0d22; border:1px solid #1e1e3a; border-left:3px solid #A100F2;
    border-radius:10px; padding:12px 16px; margin:6px 0;
}
.tc-card h4 { color:#b060ff !important; margin:0 0 6px !important; font-size:0.9rem !important; }
.tc-card p  { color:#c8c8e8 !important; font-size:0.85rem !important; margin:0 !important; }

.welcome {
    background:#0f0f22; border:1px solid #252545; border-radius:16px;
    padding:28px 32px; margin:20px 0; text-align:center;
}
.welcome h2 { color:#c080ff !important; font-size:1.4rem !important; margin:0 0 10px !important; }
.welcome p  { color:#b0b0cc !important; font-size:0.95rem !important; margin:4px 0 !important; }
.welcome .example { color:#A100F2 !important; font-style:italic; }

.footer { text-align:center; color:#333355; font-size:0.72rem; padding:16px 0 4px; }
.footer span { color:#A100F2; font-weight:700; }

[data-testid="stExpanderToggleIcon"] { display: none !important; }
[data-testid="stExpander"] summary svg { display: none !important; }
[data-testid="stExpander"] details summary::marker { display: none !important; }
[data-testid="stExpander"] details > summary > div > svg { display: none !important; }
[data-testid="stExpander"] details > summary span[data-testid="stExpanderToggleIcon"],
[data-testid="stExpander"] details > summary > div > span { display: none !important; }
/* kill Material Icons ligature text (arrow_down) */
[data-testid="stExpander"] details summary [data-testid="stExpanderToggleIcon"] *,
[data-testid="stExpander"] details summary .eyeIcon,
[data-testid="stExpander"] details summary span { font-size: 0 !important; width: 0 !important; overflow: hidden !important; }
[data-testid^="stBaseButton-"] {
    background: transparent !important; background-color: transparent !important;
    color: #A100F2 !important; border: 1.5px solid #A100F2 !important;
    border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="delegate-header">
    <h1>🤖 Quality Engineering Delegate</h1>
    <p>Agentic Quality Engineering Orchestrator — objective-driven, INVEST-validated</p>
    <span class="badge">⚡ Accenture QEAF 2.0</span>
</div>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for k, v in [("d_messages", []), ("d_state", "IDLE"), ("d_session_id", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── LLM config panel ─────────────────────────────────────────────────────────
with st.expander("⚙️ LLM Configuration", expanded=not st.session_state.d_messages):
    c1, c2, c3, c4, c5 = st.columns([1, 1.2, 2.5, 0.8, 1])
    with c1:
        provider = st.selectbox("Provider", ["openai", "gemini"], key="d_prov")
    with c2:
        model = st.selectbox("Model",
            ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"] if provider == "openai" else ["gemini-pro"],
            key="d_model")
    with c3:
        api_key = st.text_input("API Key", type="password", key="d_key")
    with c4:
        temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.01, key="d_temp")
    with c5:
        max_tokens = st.number_input("Max Tokens", 500, 4000, 2000, 100, key="d_tokens")

# ── Jira config panel ─────────────────────────────────────────────────────────
with st.expander("🔗 Jira Configuration (optional — for Story ID input)", expanded=False):
    j1, j2, j3 = st.columns([2, 2, 2])
    with j1:
        jira_url = st.text_input("Jira URL", placeholder="https://yourorg.atlassian.net", key="d_jira_url")
    with j2:
        jira_email = st.text_input("Email", placeholder="you@example.com", key="d_jira_email")
    with j3:
        jira_pat = st.text_input("API Token / PAT", type="password", key="d_jira_pat")

# ── Welcome screen ────────────────────────────────────────────────────────────
if not st.session_state.d_messages:
    st.markdown("""
    <div class="welcome">
        <h2>👋 Welcome to Quality Engineering Delegate</h2>
        <p>Tell me your <strong>testing objective</strong> and I'll guide you through:</p>
        <p>📋 Requirement collection &nbsp;→&nbsp; 🔍 INVEST validation &nbsp;→&nbsp; 🧪 Test case generation</p>
        <p style="margin-top:10px;font-size:0.85rem">You can provide requirements as <strong>plain text</strong> or as <strong>Jira Story IDs</strong> (e.g. <span class="example">PROJ-123, PROJ-124</span>)</p>
        <br>
    </div>
    """, unsafe_allow_html=True)

# ── Chat history ──────────────────────────────────────────────────────────────
for msg in st.session_state.d_messages:
    if msg["role"] == "user":
        st.markdown(f'<div class="bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
    else:
        import re as _re
        state = msg.get("state", "")
        content_html = msg["content"].replace(chr(10), "<br>")
        content_html = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content_html)
        st.markdown(f"""
        <div class="bubble-bot">
            <span class="state-pill s-{state}">● {state.replace('_',' ')}</span><br>
            {content_html}
        </div>
        """, unsafe_allow_html=True)

        if msg.get("assessment"):
            with st.expander(f"📊 INVEST Assessment — {len(msg['assessment'])} requirement(s)"):
                for r in msg["assessment"]:
                    icon = "✅" if r["verdict"] == "pass" else "❌"
                    verdict_color = "#60dd60" if r["verdict"] == "pass" else "#ff6666"
                    st.markdown(f'<div style="color:{verdict_color};font-weight:700;font-size:0.95rem;margin:8px 0 4px">{icon} {r["requirement"][:120]}</div>', unsafe_allow_html=True)
                    scores = r.get("invest_scores", {})
                    score_html = " ".join(
                        f'<span style="margin-right:14px;color:#e0e0ff"><b style="color:#ffffff">{k[0]}</b> {"✅" if v else "❌"}</span>'
                        for k, v in scores.items()
                    )
                    st.markdown(f'<div style="margin:6px 0 4px;font-size:0.9rem">{score_html}</div>', unsafe_allow_html=True)
                    if r.get("reasons"):
                        st.markdown(f'<div style="color:#ffcc66;font-size:0.82rem;margin:4px 0 8px">⚠️ {" | ".join(r["reasons"])}</div>', unsafe_allow_html=True)
                    st.divider()

        if msg.get("test_cases"):
            with st.expander(f"🧪 {len(msg['test_cases'])} Generated Test Cases"):
                for i, tc in enumerate(msg["test_cases"], 1):
                    st.markdown(f"""
                    <div class="tc-card">
                        <h4>{tc.get('test_order', i)}. {tc.get('title','')}</h4>
                        <p><em>{tc.get('objective','')}</em></p>
                        <p>{tc.get('description','')}</p>
                        <p style="font-size:0.78rem;color:#a070ff;margin-top:6px">
                            📌 {tc.get('module_name','')} &nbsp;|&nbsp; 🧪 {tc.get('test_type','')}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
            # make available in main QEAF app session
            st.session_state.test_cases = msg["test_cases"]

# ── Reset button ──────────────────────────────────────────────────────────────
if st.session_state.d_messages:
    if st.button("🔄 Reset Conversation"):
        st.session_state.d_messages = []
        st.session_state.d_state = "IDLE"
        st.session_state.d_session_id = None
        st.rerun()

# ── Chat input ────────────────────────────────────────────────────────────────
user_input = st.chat_input("Type your objective or reply here...")

if user_input:
    if not api_key:
        st.error("Please enter your API key in the LLM Configuration panel above.")
    else:
        st.session_state.d_messages.append({"role": "user", "content": user_input})
        with st.spinner("QE Delegate is thinking..."):
            try:
                resp = requests.post(f"{API_URL}/api/orchestrate", json={
                    "message": user_input,
                    "session_id": st.session_state.d_session_id,
                    "state": st.session_state.d_state,
                    "llm_config": {
                        "provider": provider, "model": model, "api_key": api_key,
                        "temperature": float(temperature), "max_tokens": int(max_tokens)
                    },
                    "jira_config": {
                        "jira_url": jira_url, "email": jira_email, "pat": jira_pat
                    } if jira_url and jira_email and jira_pat else None
                }, timeout=180)
                resp.raise_for_status()
                data = resp.json()
                st.session_state.d_state = data.get("state", "IDLE")
                st.session_state.d_session_id = data.get("session_id")
                st.session_state.d_messages.append({
                    "role": "bot",
                    "content": data.get("reply", ""),
                    "state": data.get("state", ""),
                    "assessment": data.get("assessment", []),
                    "test_cases": data.get("test_cases", [])
                })
            except Exception as e:
                st.error(f"Error communicating with backend: {e}")
        st.rerun()

st.markdown('<div class="footer">Powered by <span>Accenture</span> Quality Engineering Agentic Framework 2.0</div>',
            unsafe_allow_html=True)
