
import os
import sys
import time
import base64
import streamlit as st
import importlib.util
from pathlib import Path

# --- Universal Project Root Detection ---
def find_project_root():
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "requirements.txt").exists() or (parent / ".git").exists():
            return parent
    return here.parent

PROJECT_ROOT = find_project_root()
UI_DIR = PROJECT_ROOT / "quality_engineering_agentic_framework" / "web" / "ui"

manual_path = UI_DIR / "referenceDoc" / "QEAgenticFramework_UserManual_V0.1.pdf"
manual_link = "?doc=manual"

query_params = st.query_params
if query_params.get("doc") == "manual" and manual_path.exists():
    manual_b64 = base64.b64encode(manual_path.read_bytes()).decode("utf-8")
    st.markdown(
        f"""
        <iframe src="data:application/pdf;base64,{manual_b64}" width="100%" height="900px" style="border:0;"></iframe>
        """,
        unsafe_allow_html=True,
    )
    st.stop()


st.set_page_config(
    page_title="Quality Engineering Agentic Framework",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load shared CSS from file (always from UI_DIR)
shared_css_path = UI_DIR / "shared_styles.css"
with open(shared_css_path, encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Default placeholder image (always from UI_DIR/img)
IMAGE_URL = os.environ.get(
    "LOGIN_IMAGE_URL",
    str(UI_DIR / "img" / "Image of.png"),
)

# Initialize session flags
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "remember" not in st.session_state:
    st.session_state.remember = False

# Dynamically import app.py as main_app_module (always from UI_DIR)
app_path = UI_DIR / "app.py"
spec = importlib.util.spec_from_file_location("main_app_module", str(app_path))
main_app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_app_module)

if st.session_state.authenticated:
    with st.sidebar:
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.rerun()
    main_app_module.main()
else:
    # --- Main Layout ---
    col_left, col_right = st.columns([2, 3], gap="large")
    with col_left:
        st.markdown("""
            <span style='font-size:2.1em; font-weight:600; color:#7B2FF2;'>Welcome to QEAF</span><br>
            <span style='font-size:2.5em; font-weight:700;'>Reinvent Quality Engineering with <span style='color:#7B2FF2;'>Open‑Source Agentic AI</span></span>
        """, unsafe_allow_html=True)
        st.write("Quality Engineering Agentic Framework (QEAF) is an open‑source, agentic GenAI platform that unifies end‑to‑end intelligent automation across the test delivery lifecycle—helping enterprises transform Quality Engineering with speed, scale, and measurable outcomes.")
        st.write("")
        if 'show_login' not in st.session_state:
            st.session_state.show_login = False
        col_btn1, col_btn2 = st.columns([1,2], gap="small")
        with col_btn1:
            if st.button("Login →", key="show_login_btn", use_container_width=True):
                st.session_state.show_login = not st.session_state.show_login
        st.markdown("<div style='height: 2px;'></div>", unsafe_allow_html=True)
    with col_right:
        if not st.session_state.show_login:
            gif_path = UI_DIR / "img" / "qeaf_animation.gif"
            if gif_path.exists():
                st.image(str(gif_path), use_container_width=True)
            else:
                st.info("[QEAF Animation GIF missing: img/qeaf_animation.gif]")
        else:
            with st.form(key="login_form"):
                identifier = st.text_input("Email or Phone / Username", value="", placeholder="Admin")
                password = st.text_input("Password", value="", type="password", placeholder="Password", label_visibility="visible")
                remember = st.checkbox("Remember me", value=False)
                st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
                submit_button = st.form_submit_button("Login", type="primary", use_container_width=True)
                if submit_button:
                    if identifier.strip() == "Admin" and password == "Password":
                        st.session_state.authenticated = True
                        st.session_state.remember = remember
                        st.success("Login successful")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
            st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("<br><br>", unsafe_allow_html=True)
    # --- Info Cards ---
    card_col1, card_col2, card_col3 = st.columns(3)
    card_style = """
        <div style='min-height: 110px; display: flex; align-items: center; justify-content: center; padding: 0.5em 0;'>
            {content}
        </div>
    """
    with card_col1:
        with st.container():
            st.markdown(
                f"""
                <div class="custom-info-card">
                    <span class="info-icon">ℹ️ </span>
                    <span class="info-title">New to QEAF? Then </span>
                    <span class="info-link">
                        <a href="{manual_link}" target="_blank" rel="noopener noreferrer">
                        click here.
                        </a>
                    </span>
                </div>
                """,
                unsafe_allow_html=True
        )

    with card_col2:
        with st.container():
            st.markdown(
                '''
                <div class="custom-info-card">
                    <span class="info-icon">📩</span>
                    <span class="info-title">Any queries? Please contact the team\n@ <a href="mailto:your-email@domain.com" class="info-link">your-email@domain.com</a>.</span>
                </div>
                ''',
                unsafe_allow_html=True
            )
    with card_col3:
        with st.container():
            st.markdown(
                '''
                <div class="custom-info-card">
                    <span class="info-icon">🎓</span>
                    <span class="info-title">Learn GenAI\nEnroll for GenAI in TDLC training and get access to GenWizard learning environment</span>
                </div>
                ''',
                unsafe_allow_html=True
            )
           
