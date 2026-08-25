# Tiger Analytics brand tokens, color palette, and theme detection
# Co-authored with CoCo
import streamlit as st

TA_ORANGE = "#F15A22"
TA_ORANGE_DARK = "#D94E1C"
TA_NAVY = "#1A1A2E"
TA_GREY_100 = "#F5F5F5"
TA_GREY_200 = "#E0E0E0"
TA_GREY_700 = "#4A4A68"
TA_TEXT_LIGHT = "#1A1A2E"
TA_TEXT_DARK = "#E6EDF3"
TA_DARK_BG = "#0D1117"
TA_DARK_SURFACE = "#161B22"
TA_DARK_BORDER = "#2D333B"
TA_DARK_TEXT_MUTED = "#8B949E"

CHART_COLORS = [
    "#F15A22", "#2196F3", "#4CAF50", "#FF9800",
    "#9C27B0", "#00BCD4", "#E91E63", "#8BC34A",
]

CORTEX_MODELS = ["claude-sonnet-4-6", "llama3.3-70b", "mistral-large3", "claude-haiku-4-5"]


def get_available_cortex_models(session=None) -> list[str]:
    """Query Snowflake for available Cortex LLM models.

    Tries SHOW CORTEX BASE MODELS first.  If empty, probes known models with
    a trivial COMPLETE call.  Falls back to the hardcoded list on failure.
    """
    if session is None:
        return CORTEX_MODELS
    try:
        # Method 1: SHOW CORTEX BASE MODELS
        df = session.sql("SHOW CORTEX BASE MODELS").collect()
        if df:
            models = []
            for row in df:
                name = row["name"]
                status = str(row.get("lifecycle_status", "") or "")
                if status.upper() not in ("LEGACY", "DEPRECATED", "EOL"):
                    models.append(name)
            # Exclude embedding-only models
            complete_models = [
                m for m in models
                if not any(x in m for x in ("embed", "nv-embed",
                                             "multilingual-e5", "voyage"))
            ]
            if complete_models:
                return sorted(complete_models)
    except Exception:
        pass

    # Method 2: Probe known models with a trivial call
    try:
        probe_models = CORTEX_MODELS + [
            "llama3.1-8b", "llama3.1-70b", "mistral-large",
            "claude-3-5-sonnet", "snowflake-arctic",
        ]
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for m in probe_models:
            if m not in seen:
                seen.add(m)
                unique.append(m)
        available = []
        for model in unique:
            try:
                session.sql(
                    f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', 'hi')"
                ).collect()
                available.append(model)
            except Exception:
                continue
        if available:
            return available
    except Exception:
        pass

    return CORTEX_MODELS


def _is_dark_color(hex_color: str) -> bool:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return False
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 < 0.5


def get_active_theme() -> str:
    try:
        bg = st.get_option("theme.backgroundColor")
        if bg and _is_dark_color(bg):
            return "dark"
        if bg:
            return "light"
    except Exception:
        pass
    return "light"


def get_theme_tokens() -> dict:
    is_dark = get_active_theme() == "dark"
    return {
        "is_dark": is_dark,
        "accent": TA_ORANGE,
        "accent_hover": TA_ORANGE_DARK,
        "bg": TA_DARK_BG if is_dark else "#FFFFFF",
        "bg2": TA_DARK_SURFACE if is_dark else TA_GREY_100,
        "text": TA_TEXT_DARK if is_dark else TA_TEXT_LIGHT,
        "text_muted": TA_DARK_TEXT_MUTED if is_dark else TA_GREY_700,
        "border": TA_DARK_BORDER if is_dark else TA_GREY_200,
        "card_bg": TA_DARK_SURFACE if is_dark else TA_GREY_100,
        "sidebar_bg": "#010409" if is_dark else TA_NAVY,
        "sidebar_text": TA_TEXT_DARK if is_dark else "#FFFFFF",
    }
