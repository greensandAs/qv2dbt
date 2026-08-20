# Conversion page — DDL, Views, dbt, Procedures with Run in Snowflake + ZIP export
# Co-authored with CoCo
import streamlit as st
import engine_bridge as eb


def render(session):
    st.header("5 · Conversion")
    a = st.session_state.get("analysis")
    if not a:
        st.info("Upload and parse a script on page 1 first.")
        return

    st.write("Generate and execute Snowflake SQL from parsed QlikView tables.")

    # Table and output type selection
    col1, col2 = st.columns([2, 1])
    with col1:
        table_names = [t.name for t in a.script.tables]
        selected_tables = st.multiselect(
            "Select tables to convert",
            table_names,
            default=table_names,
        )
    with col2:
        output_types = st.multiselect(
            "Output formats",
            ["create_table", "view", "dbt", "procedure", "select"],
            default=["create_table", "view", "dbt"],
        )

    if not selected_tables or not output_types:
        st.info("Select tables and output formats above.")
        return

    # Generate conversions
    try:
        converter = eb.Converter(a)
    except Exception as e:
        st.error(f"Error initialising converter: {e}")
        return

    all_sql = {}
    for tbl_name in selected_tables:
        table = next((t for t in a.script.tables if t.name == tbl_name), None)
        if table:
            try:
                all_sql[tbl_name] = converter.convert(table, output_types)
            except Exception as e:
                st.warning(f"Could not convert {tbl_name}: {e}")

    if not all_sql:
        st.warning("No conversions generated.")
        return

    # Display in tabs by output type
    type_labels = {
        "create_table": "CREATE TABLE DDL",
        "view": "CREATE VIEW",
        "dbt": "dbt Models",
        "procedure": "Stored Procedures",
        "select": "SELECT Statements",
    }
    tabs = st.tabs([type_labels.get(t, t) for t in output_types])

    for tab, otype in zip(tabs, output_types):
        with tab:
            for tbl_name, outputs in all_sql.items():
                sql = outputs.get(otype)
                if sql:
                    with st.expander(f"{tbl_name}", expanded=len(selected_tables) <= 5):
                        st.code(sql, language="sql")

                        # Run in Snowflake button
                        btn_key = f"run_{otype}_{tbl_name}"
                        if otype in ("create_table", "view", "procedure"):
                            if st.button(
                                f"Run in Snowflake",
                                key=btn_key,
                                type="secondary",
                            ):
                                _execute_sql(session, sql, tbl_name, otype)

    # Export section
    st.divider()
    st.subheader("Export")

    col_a, col_b = st.columns(2)
    with col_a:
        # Combined SQL download
        combined_parts = []
        for tbl_name, outputs in all_sql.items():
            combined_parts.append(f"-- === {tbl_name} ===")
            for otype, sql in outputs.items():
                combined_parts.append(f"-- [{otype}]")
                combined_parts.append(sql)
                combined_parts.append("")
        combined = "\n".join(combined_parts)
        st.download_button(
            "Download All SQL",
            combined,
            file_name="qv2dbt_conversion.sql",
        )

    with col_b:
        # Full ZIP export
        if st.button("Export Full ZIP (dbt + DDL + STTM + Lineage)", type="primary"):
            analyses = st.session_state.get("all_analyses", [a])
            primary = analyses[0]
            with st.spinner("Running full pipeline and packaging ZIP..."):
                try:
                    # Get original file bytes from session
                    zip_bytes = eb.full_run_zip(
                        primary.text.encode("utf-8"), primary.name
                    )
                    st.download_button(
                        "Download ZIP",
                        zip_bytes,
                        file_name=f"{primary.name.rsplit('.', 1)[0]}_migration.zip",
                        mime="application/zip",
                    )
                except Exception as e:
                    st.error(f"ZIP export failed: {e}")


def _execute_sql(session, sql: str, table_name: str, output_type: str):
    """Execute SQL in Snowflake with error handling."""
    try:
        with st.spinner(f"Executing {output_type} for {table_name}..."):
            # Split on semicolons for multi-statement execution
            statements = [s.strip() for s in sql.split(";") if s.strip()
                          and not s.strip().startswith("--")]
            for stmt in statements:
                session.sql(stmt).collect()
        st.success(f"Executed {output_type} for **{table_name}** successfully.")
    except Exception as e:
        st.error(f"Execution failed for {table_name}: {e}")
