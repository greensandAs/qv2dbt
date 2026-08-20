# CSS injection for Tiger Analytics branded styling
# Co-authored with CoCo
import streamlit as st
from config.brand import TA_ORANGE, TA_ORANGE_DARK, get_theme_tokens


def inject_styles():
    t = get_theme_tokens()
    st.markdown(f"""
<style>
    .stApp {{ background-color: {t["bg"]}; color: {t["text"]}; font-family: 'Source Sans Pro', sans-serif; }}
    [data-testid="stAppViewContainer"] {{ background-color: {t["bg"]}; color: {t["text"]}; }}
    h1, h2, h3, h4, h5, h6 {{ color: {t["text"]}; }}
    section[data-testid="stSidebar"] {{ background-color: {t["sidebar_bg"]}; color: {t["sidebar_text"]}; }}
    section[data-testid="stSidebar"] > div:first-child {{ border-top: 4px solid {t["accent"]}; }}
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] .stRadio label,
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label p {{ color: {t["sidebar_text"]} !important; }}
    div[data-testid="stMetric"] {{ background-color: {t["card_bg"]}; border-left: 4px solid {t["accent"]}; border-radius: 8px; padding: 12px 16px; }}
    .stButton > button {{ background-color: {TA_ORANGE}; color: #FFFFFF; border: none; border-radius: 6px; font-weight: 600; }}
    .stButton > button:hover {{ background-color: {TA_ORANGE_DARK}; color: #FFFFFF; }}
    .stDownloadButton > button {{ background-color: {TA_ORANGE}; color: #FFFFFF !important; border: none; border-radius: 6px; font-weight: 600; }}
    .stTabs [aria-selected="true"] {{ border-bottom-color: {TA_ORANGE} !important; color: {TA_ORANGE} !important; }}
    a {{ color: {TA_ORANGE}; }}
    div.block-container {{ padding-top: 1.5rem; }}
</style>
""", unsafe_allow_html=True)
