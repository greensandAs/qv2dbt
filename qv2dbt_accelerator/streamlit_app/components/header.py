# Header component for Tiger Analytics branding
# Co-authored with CoCo
import streamlit as st
from config.brand import TA_ORANGE, get_theme_tokens


def render_header():
    t = get_theme_tokens()
    col_logo, col_title = st.columns([1, 5])
    with col_logo:
        st.markdown(
            f'<div style="font-size:2.5rem;font-weight:bold;color:{TA_ORANGE};">🐯</div>',
            unsafe_allow_html=True,
        )
    with col_title:
        st.markdown(
            f'<h2 style="margin:0;padding:0;font-size:1.6rem;font-weight:700;color:{t["text"]};">'
            f'qv2dbt Studio <span style="font-size:0.8rem;color:{t["text_muted"]};">'
            f'| QlikView → Snowflake</span></h2>',
            unsafe_allow_html=True,
        )


def render_footer():
    t = get_theme_tokens()
    st.markdown("---")
    st.markdown(
        f'<p style="text-align:center; color:{t["text_muted"]}; font-size:0.8rem;">'
        f'Powered by <span style="color:{TA_ORANGE}; font-weight:600;">Tiger Analytics</span>'
        f' · Built on Snowflake · qv2dbt Accelerator v1.0</p>',
        unsafe_allow_html=True,
    )
