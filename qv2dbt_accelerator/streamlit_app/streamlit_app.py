# qv2dbt Studio — Tiger Analytics branded QlikView to Snowflake migration app
# Co-authored with CoCo
"""
Thin orchestrator: page config, session init, persistence controls, then
delegates to modular components (config/, components/, app_pages/).
"""
import os

import streamlit as st

from components import inject_styles, render_header, render_sidebar, render_footer
from app_pages import upload, inventory, lineage, sttm, conversion, chatbot
import snowflake_utils as sf

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Tiger Analytics | qv2dbt Studio",
    page_icon="🐯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Global Styles ────────────────────────────────────────────────────────────
inject_styles()

# ─── Snowflake Connection (optional for local mode) ──────────────────────────
session = None
try:
    conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
    session = conn.session()
except Exception:
    st.sidebar.warning("No Snowflake connection. Cortex AI and Run-in-SF disabled.")

# ─── Session State Defaults ───────────────────────────────────────────────────
st.session_state.setdefault("analysis", None)
st.session_state.setdefault("all_analyses", [])
st.session_state.setdefault("chat", [])
st.session_state.setdefault("cortex_model", "mistral-large2")

# ─── Layout ───────────────────────────────────────────────────────────────────
render_header()
page = render_sidebar()

# ─── Persistence Controls (sidebar bottom) ────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.markdown("**Session**")
    col_s, col_l = st.columns(2)
    with col_s:
        if st.button("Save", use_container_width=True):
            a = st.session_state.get("analysis")
            if a:
                try:
                    path = sf.save_analysis(session, a)
                    st.toast(f"Saved to {path}", icon="💾")
                except Exception as e:
                    st.toast(f"Save failed: {e}", icon="❌")
            else:
                st.toast("Nothing to save — parse a script first.", icon="⚠️")
    with col_l:
        if st.button("Load", use_container_width=True):
            st.session_state["show_load_dialog"] = True

    if st.session_state.get("show_load_dialog"):
        saved = sf.list_saved_analyses(session)
        if saved:
            names = [s["name"] for s in saved]
            pick = st.selectbox("Saved analyses", names, key="load_picker")
            if st.button("Restore", key="restore_btn"):
                data = sf.load_saved_analysis(session, pick)
                if data:
                    st.toast(f"Loaded {data.get('name', 'analysis')}", icon="✅")
                    st.session_state["show_load_dialog"] = False
                else:
                    st.toast("Could not load file.", icon="❌")
        else:
            st.caption("No saved analyses found.")

# ─── Page Router ──────────────────────────────────────────────────────────────
PAGE_MAP = {
    "1 · Upload & Parse": upload.render,
    "2 · Inventory": inventory.render,
    "3 · Lineage": lineage.render,
    "4 · STTM": sttm.render,
    "5 · Conversion": conversion.render,
    "6 · Chatbot": chatbot.render,
}

PAGE_MAP[page](session)

# ─── Footer ──────────────────────────────────────────────────────────────────
render_footer()
