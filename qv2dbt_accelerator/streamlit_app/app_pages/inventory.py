# Inventory page with error boundaries and effort scoring
# Co-authored with CoCo
import pandas as pd
import streamlit as st
import engine_bridge as eb


def render(session):
    st.header("2 · Inventory")
    a = st.session_state.get("analysis")
    if not a:
        st.info("Upload and parse a script on page 1 first.")
        return

    try:
        inv = eb.inventory(a)
    except Exception as e:
        st.error(f"Error building inventory: {e}")
        return

    # Layer distribution
    st.subheader("Layer Distribution")
    counts = inv["counts"]
    cols = st.columns(5)
    cols[0].metric("Staging", counts.get("staging", 0))
    cols[1].metric("Intermediate", counts.get("intermediate", 0))
    cols[2].metric("Mart (Target)", counts.get("target_tables", 0))
    cols[3].metric("Mapping", counts.get("mapping", 0))
    cols[4].metric("Variables", counts.get("variables", 0))

    # Table details
    st.subheader("Table Details")
    if inv.get("tables"):
        st.dataframe(
            pd.DataFrame(inv["tables"]),
            hide_index=True, use_container_width=True,
        )

    # Effort scoring
    st.subheader("Migration Effort Estimate")
    try:
        scores = eb.effort_scores(a)
        if scores:
            df = pd.DataFrame(scores)
            st.dataframe(df, hide_index=True, use_container_width=True)

            # Summary by complexity
            summary = df["Complexity"].value_counts().to_dict()
            c = st.columns(3)
            c[0].metric("Low Complexity", summary.get("Low", 0))
            c[1].metric("Medium Complexity", summary.get("Medium", 0))
            c[2].metric("High Complexity", summary.get("High", 0))
    except Exception as e:
        st.warning(f"Could not compute effort scores: {e}")

    # Control flow blocks
    if inv.get("control_blocks"):
        st.subheader("Control Flow (requires manual review)")
        st.json(inv["control_blocks"])

    # Variables
    if inv.get("variables"):
        with st.expander(f"Script Variables ({len(inv['variables'])})"):
            st.dataframe(
                pd.DataFrame(inv["variables"]),
                hide_index=True, use_container_width=True,
            )
