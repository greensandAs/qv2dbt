# Upload & Parse page with multi-file support and progress indicators
# Co-authored with CoCo
import pandas as pd
import streamlit as st
import engine_bridge as eb


def render(session):
    st.header("1 · Upload & Parse")
    st.write(
        "Upload **.qvf / .qvw** apps or **.qvs / .txt** load scripts. "
        f"Max {eb.MAX_FILE_SIZE_MB} MB per file."
    )

    uploaded_files = st.file_uploader(
        "Script or app files",
        type=["qvf", "qvw", "qvs", "txt"],
        accept_multiple_files=True,
    )

    if uploaded_files and st.button("Parse All", type="primary"):
        analyses = []
        progress = st.progress(0, text="Parsing...")
        total = len(uploaded_files)

        for idx, up in enumerate(uploaded_files):
            progress.progress(
                (idx) / total,
                text=f"Parsing {up.name} ({idx + 1}/{total})...",
            )
            try:
                a = eb.analyze(up.getvalue(), up.name)
                analyses.append(a)
                st.toast(f"Parsed {up.name}", icon="✅")
            except eb.ValidationError as e:
                st.error(f"**{up.name}** — Validation error: {e}")
            except eb.ParseError as e:
                st.error(f"**{up.name}** — Parse error: {e}")
            except Exception as e:
                st.error(f"**{up.name}** — Unexpected error: {e}")

        progress.progress(1.0, text="Done!")

        if analyses:
            # Use first analysis as primary; store all for multi-file
            st.session_state.analysis = analyses[0]
            st.session_state.all_analyses = analyses
            st.success(f"Successfully parsed {len(analyses)}/{total} file(s).")

    # Display current state
    analyses = st.session_state.get("all_analyses", [])
    primary = st.session_state.get("analysis")

    if not primary:
        st.info("No script parsed yet. Upload file(s) above.")
        return

    # Multi-file selector
    if len(analyses) > 1:
        names = [a.name for a in analyses]
        selected = st.selectbox("Active script", names, index=0)
        st.session_state.analysis = next(a for a in analyses if a.name == selected)
        primary = st.session_state.analysis

    # Summary metrics
    st.success(
        f"Parsed **{primary.name}** — {len(primary.script.tables)} tables, "
        f"{len(primary.tabs)} pages."
    )
    pct = eb.auto_pct(primary)
    m = st.columns(4)
    m[0].metric("Tables", len(primary.script.tables))
    m[1].metric("Source Tables", sum(
        1 for t in primary.script.tables
        if t.kind in (eb.LoadKind.QVD, eb.LoadKind.FILE, eb.LoadKind.SQL)
    ))
    m[2].metric("Target Tables", sum(
        1 for t in primary.script.tables if t.layer == "mart"
    ))
    m[3].metric("Auto-translatable", f"{pct:.0f}%")

    if primary.tabs:
        st.subheader("Pages (script tabs)")
        st.dataframe(
            pd.DataFrame({"#": range(1, len(primary.tabs) + 1), "Tab": primary.tabs}),
            hide_index=True, use_container_width=True,
        )

    with st.expander("View extracted script"):
        st.code(primary.text[:30000], language="sql")
