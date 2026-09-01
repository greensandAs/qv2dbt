# Sidebar navigation component
from pathlib import Path
import streamlit as st
from config.brand import TA_ORANGE, CORTEX_MODELS, get_available_cortex_models, get_theme_tokens

PAGES = [
    "1 · Upload & Parse",
    "2 · Inventory",
    "3 · Lineage",
    "4 · STTM",
    "5 · Conversion",
    "6 · Chatbot",
    "7 · CoCo Assistant",
]


def render_sidebar() -> str:
    t = get_theme_tokens()
    sb_text = t["sidebar_text"]

    logo_path = (
        Path(__file__).resolve().parents[2]
        / "assets"
        / "logos"
        / "ta_logo_dark.svg"
    )

    with st.sidebar:
        st.image(str(logo_path), width=190)
        st.markdown(
            f'<p style="text-align:center;font-size:0.75rem;color:{sb_text};opacity:0.7;">'
            f'QlikView → Snowflake Migration</p>',
            unsafe_allow_html=True,
        )
        st.markdown("---")

        page = st.radio("Navigation", PAGES, label_visibility="collapsed")

        st.markdown("---")
        # Use cached model list (probed once per session, not every render)
        try:
            if "available_cortex_models" not in st.session_state:
                session = st.session_state.get("snowflake_session")
                st.session_state["available_cortex_models"] = get_available_cortex_models(session)
            available_models = st.session_state["available_cortex_models"]
        except Exception:
            available_models = CORTEX_MODELS
        current_model = st.session_state.get("cortex_model", available_models[0])
        if current_model not in available_models:
            current_model = available_models[0]
        st.session_state.cortex_model = st.selectbox(
            "Cortex Model", available_models,
            index=available_models.index(current_model),
        )

        st.markdown("---")
        st.markdown(
            f'<p style="font-size:0.7rem;color:{sb_text};opacity:0.5;text-align:center;">'
            f'Powered by Tiger Analytics<br>Built on Snowflake</p>',
            unsafe_allow_html=True,
        )

    return page
