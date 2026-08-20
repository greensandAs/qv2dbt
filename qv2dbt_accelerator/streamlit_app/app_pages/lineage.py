# Lineage page with error boundaries
# Co-authored with CoCo
import pandas as pd
import streamlit as st
import engine_bridge as eb


def render(session):
    st.header("3 · Lineage")
    a = st.session_state.get("analysis")
    if not a:
        st.info("Upload and parse a script on page 1 first.")
        return

    st.write("Column-level lineage tracing QlikView sources → Snowflake targets.")

    try:
        rows = eb.lineage_rows(a)
    except Exception as e:
        st.error(f"Error building lineage: {e}")
        return

    if not rows:
        st.info("No lineage data available for this script.")
        return

    df = pd.DataFrame(rows)

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        tables = sorted(df["Target Table"].unique().tolist())
        picked_tables = st.multiselect("Filter by target table", tables, default=tables[:5])
    with col2:
        layers = sorted(df["Layer"].unique().tolist())
        picked_layers = st.multiselect("Filter by layer", layers, default=layers)
    with col3:
        show_review_only = st.checkbox("Only items needing review", value=False)

    # Apply filters
    filtered = df.copy()
    if picked_tables:
        filtered = filtered[filtered["Target Table"].isin(picked_tables)]
    if picked_layers:
        filtered = filtered[filtered["Layer"].isin(picked_layers)]
    if show_review_only:
        filtered = filtered[filtered["Needs Review"] == "Yes"]

    st.caption(f"{len(filtered)} of {len(df)} column mappings shown")
    st.dataframe(filtered, hide_index=True, use_container_width=True)

    # Download lineage CSV
    csv = filtered.to_csv(index=False)
    st.download_button(
        "Download Lineage CSV",
        csv,
        file_name="lineage.csv",
        mime="text/csv",
    )
