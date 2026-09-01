# Lineage page with error boundaries
# Co-authored with CoCo
import json as _json

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

    # --- OpenLineage Events ---
    st.divider()
    st.subheader("OpenLineage Events (spec v2-0-2)")
    st.caption("Standard-format lineage events for ingestion into Marquez, "
               "Atlan, DataHub, or Snowflake Horizon.")

    try:
        from qv2dbt.generators.openlineage import build_events
        ol_events = build_events(a.script, a.lineage, a.config)
    except Exception as e:
        st.error(f"Error generating OpenLineage events: {e}")
        return

    summary_rows = []
    for ev in ol_events:
        job = ev["job"]["name"]
        n_in = len(ev["inputs"])
        cl = ev["outputs"][0].get("facets", {}).get("columnLineage", {})
        n_cols = len(cl.get("fields", {}))
        summary_rows.append({
            "Job": job,
            "Namespace": ev["job"]["namespace"],
            "Inputs": n_in,
            "Output columns": n_cols,
        })
    st.dataframe(pd.DataFrame(summary_rows), hide_index=True,
                 use_container_width=True)

    with st.expander("Preview event JSON (first selected table)"):
        picked_set = set(picked_tables) if picked_tables else set()
        matched = [e for e in ol_events if e["job"]["name"] in picked_set]
        preview = matched[0] if matched else ol_events[0] if ol_events else {}
        st.code(_json.dumps(preview, indent=2), language="json")

    ol_json = _json.dumps(ol_events, indent=2)
    st.download_button("Download openlineage_events.json", ol_json,
                       file_name="openlineage_events.json",
                       mime="application/json")
