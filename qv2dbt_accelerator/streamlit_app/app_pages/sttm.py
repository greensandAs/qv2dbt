# STTM (Source-to-Target Mapping) page with error boundaries
# Co-authored with CoCo
import pandas as pd
import streamlit as st
import engine_bridge as eb


def render(session):
    st.header("4 · STTM (Source-to-Target Mapping)")
    a = st.session_state.get("analysis")
    if not a:
        st.info("Upload and parse a script on page 1 first.")
        return

    st.write("Field-level mapping: QlikView expressions → Snowflake SQL per target.")

    try:
        rows = eb.lineage_rows(a)
    except Exception as e:
        st.error(f"Error building STTM: {e}")
        return

    if not rows:
        st.info("No STTM data available.")
        return

    df = pd.DataFrame(rows)
    targets = sorted(df["Target Table"].unique().tolist())
    picked = st.multiselect("Target tables", targets, default=targets[:3])

    for name in picked:
        subset = df[df["Target Table"] == name]
        review_count = subset[subset["Needs Review"] == "Yes"].shape[0]
        header = f"{name}"
        if review_count:
            header += f" ({review_count} need review)"
        st.subheader(header)
        st.dataframe(
            subset[["Target Column", "Mapping Type", "QlikView Expression",
                    "Snowflake SQL", "Ultimate Sources", "Needs Review", "Notes"]],
            hide_index=True, use_container_width=True,
        )

    # Download full STTM
    st.divider()
    # Flatten multiline expressions to prevent CSV row corruption
    csv_df = df.copy()
    for col in ["Target Column", "QlikView Expression", "Snowflake SQL", "Notes"]:
        if col in csv_df.columns:
            csv_df[col] = csv_df[col].apply(
                lambda v: " ".join(str(v).split()) if pd.notna(v) else "")
    csv = csv_df.to_csv(index=False)
    st.download_button(
        "Download Full STTM CSV",
        csv,
        file_name="sttm_full.csv",
        mime="text/csv",
    )
