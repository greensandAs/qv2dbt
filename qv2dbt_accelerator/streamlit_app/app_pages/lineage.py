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

    # --- Table-level DAG ---
    st.subheader("Table-level lineage graph")
    st.graphviz_chart(_ol_table_dag(ol_events))

    # --- Column-level drill-down ---
    st.subheader("Column lineage drill-down")
    job_names = [ev["job"]["name"] for ev in ol_events]
    selected_job = st.selectbox("Select a table to inspect column lineage",
                                job_names)
    if selected_job:
        ev = next(e for e in ol_events if e["job"]["name"] == selected_job)
        cl = ev["outputs"][0].get("facets", {}).get("columnLineage", {})
        fields = cl.get("fields", {})
        if fields:
            st.graphviz_chart(_ol_column_dag(selected_job, fields))
            col_rows = []
            for col_name, col_info in fields.items():
                sources = ", ".join(
                    f"{f['name']}.{f['field']}" for f in col_info["inputFields"]
                )
                col_rows.append({
                    "Column": col_name,
                    "Type": col_info.get("transformationType", ""),
                    "Sources": sources,
                    "Logic": col_info.get("transformationDescription", ""),
                })
            st.dataframe(pd.DataFrame(col_rows), hide_index=True,
                         use_container_width=True)
        else:
            st.info("No column lineage for this table (e.g. mapping table).")

    # --- JSON preview & download ---
    with st.expander("Preview event JSON"):
        picked_set = set(picked_tables) if picked_tables else set()
        matched = [e for e in ol_events if e["job"]["name"] in picked_set]
        preview = matched[0] if matched else ol_events[0] if ol_events else {}
        st.code(_json.dumps(preview, indent=2), language="json")

    ol_json = _json.dumps(ol_events, indent=2)
    st.download_button("Download openlineage_events.json", ol_json,
                       file_name="openlineage_events.json",
                       mime="application/json")


# ---------------------------------------------------------------------------
# Graphviz helpers
# ---------------------------------------------------------------------------

_LAYER_COLORS = {
    "source": "#DDEBF7",   # blue
    "staging": "#E2EFDA",  # green
    "intermediate": "#FFF2CC",  # yellow
    "mart": "#FCE4D6",     # orange
    "mapping": "#E8D5F5",  # purple
}


def _ol_table_dag(events: list[dict]) -> str:
    """Build a Graphviz DOT string for the table-level OpenLineage DAG."""
    lines = [
        "digraph {",
        "  rankdir=LR;",
        "  node [shape=box, style=\"filled,rounded\", fontsize=10, fontname=Helvetica];",
        "  edge [color=\"#888888\"];",
    ]
    sources = set()
    jobs = {}
    edges = set()

    for ev in events:
        job_name = ev["job"]["name"]
        out_ns = ev["outputs"][0]["namespace"] if ev["outputs"] else ""
        # Determine layer from table metadata
        cl = ev["outputs"][0].get("facets", {}).get("columnLineage", {})
        n_cols = len(cl.get("fields", {}))
        jobs[job_name] = n_cols

        for inp in ev["inputs"]:
            src_label = inp["name"]
            is_external = "snowflake://" not in inp["namespace"]
            if is_external:
                sources.add(src_label)
            edges.add((src_label, job_name, is_external))

    # Render source nodes
    for src in sorted(sources):
        color = _LAYER_COLORS["source"]
        lines.append(f'  "{src}" [fillcolor="{color}", label="{src}\\n(source)"];')

    # Render job/table nodes
    for job_name, n_cols in jobs.items():
        color = _LAYER_COLORS.get("mart") if n_cols > 0 else _LAYER_COLORS.get("intermediate")
        label = f"{job_name}\\n({n_cols} cols)"
        lines.append(f'  "{job_name}" [fillcolor="{color}", label="{label}"];')

    # Render edges
    for src, dst, is_ext in edges:
        style = "" if is_ext else " [style=dashed]"
        lines.append(f'  "{src}" -> "{dst}"{style};')

    lines.append("}")
    return "\n".join(lines)


def _ol_column_dag(table_name: str, fields: dict) -> str:
    """Build a Graphviz DOT for column-level lineage of one table."""
    lines = [
        "digraph {",
        "  rankdir=LR;",
        "  node [fontsize=9, fontname=Helvetica];",
        "  edge [color=\"#888888\"];",
        f'  subgraph cluster_target {{',
        f'    label="{table_name}";',
        '    style="rounded,filled"; fillcolor="#FCE4D6"; color="#C55A11";',
    ]
    # Target column nodes
    for col in fields:
        nid = f"tgt_{_safe_id(col)}"
        lines.append(f'    {nid} [label="{col}", shape=box, '
                     f'style="filled,rounded", fillcolor="white"];')
    lines.append("  }")

    # Source nodes and edges
    seen_src = set()
    for col, info in fields.items():
        tgt_nid = f"tgt_{_safe_id(col)}"
        for inp in info.get("inputFields", []):
            src_label = f"{inp['name']}.{inp['field']}"
            src_nid = f"src_{_safe_id(src_label)}"
            if src_nid not in seen_src:
                seen_src.add(src_nid)
                color = _LAYER_COLORS["source"]
                lines.append(f'  {src_nid} [label="{src_label}", shape=box, '
                             f'style="filled,rounded", fillcolor="{color}"];')
            t_type = info.get("transformationType", "")
            edge_label = "direct" if t_type == "DIRECT" else ""
            lbl = f' [label="{edge_label}"]' if edge_label else ""
            lines.append(f"  {src_nid} -> {tgt_nid}{lbl};")

    lines.append("}")
    return "\n".join(lines)


def _safe_id(name: str) -> str:
    """Convert a name to a safe Graphviz node ID."""
    import re
    return "n_" + re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_")
