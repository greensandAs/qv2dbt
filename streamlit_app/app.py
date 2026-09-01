"""qv2dbt Studio — Streamlit UI for QlikView → dbt/Snowflake migration.

Pages: Upload & Parse · Inventory · Lineage · STTM · Conversion · Chatbot.
Runs standalone or inside Streamlit-in-Snowflake (session auto-detected).
Snowflake/Cortex features degrade gracefully when disconnected.
"""
from __future__ import annotations

import io
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine_bridge as eb           # noqa: E402
import snowflake_utils as sf         # noqa: E402
from qv2dbt.config import load_config  # noqa: E402

st.set_page_config(page_title="qv2dbt Studio", page_icon="🧭", layout="wide")

CORTEX_MODELS = ["mistral-large2", "llama3.1-70b", "snowflake-arctic",
                 "mixtral-8x7b"]


# ---------------------------------------------------------------------------
# session state
# ---------------------------------------------------------------------------
def _ss():
    st.session_state.setdefault("analysis", None)
    st.session_state.setdefault("config", load_config())
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("cortex_model", CORTEX_MODELS[0])


def sidebar():
    st.sidebar.title("🧭 qv2dbt Studio")
    st.sidebar.caption("QlikView → dbt / Snowflake")
    page = st.sidebar.radio(
        "Page",
        ["1 · Upload & Parse", "2 · Inventory", "3 · Lineage",
         "4 · STTM", "5 · Conversion", "6 · Chatbot"],
        label_visibility="collapsed",
    )
    st.sidebar.divider()
    # connection
    connected = sf.is_connected()
    info = sf.connection_info()
    if connected:
        st.sidebar.success(f"Snowflake: {info.get('mode')}")
        st.sidebar.caption(f"{info.get('account','?')} · {info.get('role','?')}")
    else:
        st.sidebar.warning("Snowflake: not connected")
        with st.sidebar.expander("Connect (standalone)"):
            with st.form("conn"):
                acct = st.text_input("account")
                user = st.text_input("user")
                pwd = st.text_input("password", type="password")
                role = st.text_input("role")
                wh = st.text_input("warehouse")
                db = st.text_input("database")
                if st.form_submit_button("Connect") and acct and user:
                    r = sf.connect_with(dict(account=acct, user=user,
                                             password=pwd, role=role,
                                             warehouse=wh, database=db))
                    st.rerun() if r.ok else st.error(r.error)
    st.session_state.cortex_model = st.sidebar.selectbox(
        "Cortex model", CORTEX_MODELS,
        index=CORTEX_MODELS.index(st.session_state.cortex_model))
    return page


# ---------------------------------------------------------------------------
# Page 1: Upload & Parse
# ---------------------------------------------------------------------------
def page_upload():
    st.header("1 · Upload & Parse")
    st.write("Upload a **.qvf / .qvw** app or a **.qvs / .txt** script. "
             "The script is parsed in place and its pages (tabs) are listed.")
    up = st.file_uploader("Script or app file",
                          type=["qvf", "qvw", "qvs", "txt"])
    col1, col2 = st.columns([1, 1])
    if up and col1.button("Parse", type="primary"):
        with st.spinner("Parsing…"):
            try:
                a = eb.analyze(up.getvalue(), up.name, st.session_state.config)
                st.session_state.analysis = a
            except Exception as e:
                st.error(f"Parse failed: {e}")
                return
    a = st.session_state.analysis
    if not a:
        st.info("No script parsed yet.")
        return

    st.success(f"Parsed **{a.name}** — {len(a.script.tables)} tables, "
               f"{len(a.tabs)} pages.")
    m = st.columns(4)
    inv = eb.inventory(a)
    m[0].metric("Tables", len(a.script.tables))
    m[1].metric("Source tables", inv["counts"]["source_tables"])
    m[2].metric("Target tables", inv["counts"]["target_tables (marts)"])
    m[3].metric("Control blocks", inv["counts"]["control_blocks"])

    st.subheader("Pages (script tabs)")
    if a.tabs:
        st.dataframe(pd.DataFrame({"#": range(1, len(a.tabs) + 1),
                                   "Page / Tab": a.tabs}),
                     hide_index=True, use_container_width=True)
    else:
        st.caption("No `///$tab` markers found; script has a single section.")

    with st.expander("View extracted script"):
        st.code(a.text[:20000], language="sql")
    st.download_button("⬇ Download full artifact bundle (ZIP)",
                       data=eb.full_run_zip(up.getvalue(), up.name)
                       if up else b"",
                       file_name=f"{os.path.splitext(a.name)[0]}_qv2dbt.zip",
                       disabled=up is None)


# ---------------------------------------------------------------------------
# Page 2: Inventory
# ---------------------------------------------------------------------------
def page_inventory():
    st.header("2 · Inventory")
    a = _require()
    if not a:
        return
    inv = eb.inventory(a)
    st.subheader("Counts")
    counts = inv["counts"]
    cols = st.columns(4)
    for i, (k, v) in enumerate(counts.items()):
        cols[i % 4].metric(k.replace("_", " ").title(), v)

    st.subheader("Details")
    tabs = st.tabs(["Source tables", "Target tables", "Staging",
                    "Intermediate", "Mapping", "Referred QVDs",
                    "Input files", "Output files/QVDs", "Variables",
                    "Dependencies", "Effort"])
    with tabs[0]:
        _list_df(inv["source_tables"], "Source table")
    with tabs[1]:
        _list_df(inv["target_tables"], "Target table")
    with tabs[2]:
        _list_df(inv["staging_tables"], "Staging table")
    with tabs[3]:
        _list_df(inv["intermediate_tables"], "Intermediate table")
    with tabs[4]:
        _list_df(inv["mapping_tables"], "Mapping table")
    with tabs[5]:
        _list_df(inv["referred_qvds"], "QVD")
    with tabs[6]:
        _list_df(inv["input_files"], "Input file")
    with tabs[7]:
        st.dataframe(pd.DataFrame(inv["output_files_qvds"]) if
                     inv["output_files_qvds"] else pd.DataFrame(),
                     hide_index=True, use_container_width=True)
    with tabs[8]:
        st.dataframe(pd.DataFrame(inv["variables"]), hide_index=True,
                     use_container_width=True)
    with tabs[9]:
        st.dataframe(pd.DataFrame(inv["dependencies"]) if inv["dependencies"]
                     else pd.DataFrame(columns=["from", "to", "type"]),
                     hide_index=True, use_container_width=True)
    with tabs[10]:
        eff = pd.DataFrame([eb.effort_score(t) for t in a.script.tables])
        st.dataframe(eff, hide_index=True, use_container_width=True)
        st.caption("Heuristic effort points: fields·0.2 + joins·2 + "
                   "review·3 (+2 if aggregated).")


# ---------------------------------------------------------------------------
# Page 3: Lineage
# ---------------------------------------------------------------------------
def page_lineage():
    st.header("3 · Lineage")
    a = _require()
    if not a:
        return
    lin = a.lineage
    tables = [t.name for t in a.script.tables]
    sources = sorted({f"source:{s.identifier}" for s in a.script.sources})
    options = tables + sources
    picked = st.multiselect(
        "Filter by target table(s) and/or source table/file "
        "(select one or more)", options, default=tables[:1] if tables else [])
    if not picked:
        st.info("Pick at least one table or source.")
        return

    picked_tables = {p for p in picked if not p.startswith("source:")}
    picked_srcs = {p.split("source:")[-1] for p in picked if p.startswith("source:")}

    rows = []
    for c in lin.columns:
        hit_t = c.table in picked_tables
        hit_s = any(src in picked_srcs for src, _ in c.ultimate_sources)
        if hit_t or hit_s:
            rows.append({
                "Target table": c.table, "Target column": c.column,
                "Layer": c.layer, "Mapping": c.mapping_type,
                "Source(s)": ", ".join(f"{x}.{y}" for x, y in c.ultimate_sources),
                "QlikView": c.qlik_expr, "Snowflake": c.snowflake_sql,
            })
    st.caption(f"{len(rows)} column mappings")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.subheader("Lineage graph")
    st.graphviz_chart(_dot(a, picked_tables, picked_srcs))

    # OpenLineage events section
    st.divider()
    st.subheader("OpenLineage Events (spec v2-0-2)")
    st.caption("Standard-format lineage events for ingestion into Marquez, "
               "Atlan, DataHub, or Snowflake Horizon.")
    ol_events = _openlineage_events(a)
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
        import json as _json
        matched = [e for e in ol_events if e["job"]["name"] in picked_tables]
        preview = matched[0] if matched else ol_events[0] if ol_events else {}
        st.code(_json.dumps(preview, indent=2), language="json")

    import json as _json
    ol_json = _json.dumps(ol_events, indent=2)
    st.download_button("⬇ Download openlineage_events.json", ol_json,
                       file_name="openlineage_events.json",
                       mime="application/json")


@st.cache_data(show_spinner=False)
def _openlineage_events(_a):
    from qv2dbt.generators.openlineage import build_events
    a = st.session_state.analysis
    return build_events(a.script, a.lineage, a.config)


def _dot(a, picked_tables, picked_srcs) -> str:
    lin = a.lineage
    edges = set()
    nodes = set()
    for u, d in lin.table_edges:
        du = u.split("source:")[-1]
        if (d in picked_tables or du in picked_srcs or u in
                {f"source:{s}" for s in picked_srcs} or not
                (picked_tables or picked_srcs)):
            un = du if u.startswith("source:") else u
            edges.add((un, d))
            nodes.add(un)
            nodes.add(d)
    lines = ["digraph{rankdir=LR;node[shape=box,style=rounded,fontsize=10];"]
    for n in nodes:
        color = "#DDEBF7" if n in picked_srcs else "#FCE4D6" if n in \
            picked_tables else "#FFFFFF"
        lines.append(f'"{n}"[fillcolor="{color}",style="filled,rounded"];')
    for u, d in edges:
        lines.append(f'"{u}"->"{d}";')
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Page 4: STTM
# ---------------------------------------------------------------------------
def page_sttm():
    st.header("4 · STTM (Source-to-Target Mapping)")
    a = _require()
    if not a:
        return
    targets = [t.name for t in a.script.tables]
    picked = st.multiselect("Target table(s)", targets,
                            default=[t.name for t in a.script.tables
                                     if t.layer == "mart"][:3] or targets[:1])
    for name in picked:
        t = a.script.table_by_name(name)
        cols = a.lineage.for_table(name)
        st.subheader(f"🎯 {name}  · {t.layer}")

        # business functionality
        with st.container(border=True):
            st.markdown("**Business functionality**")
            key = f"biz_{name}"
            if st.button("✨ Generate with Cortex", key=f"btn_{name}",
                         disabled=not sf.cortex_available()):
                res = sf.cortex_complete(eb.business_prompt(t, a.lineage),
                                         model=st.session_state.cortex_model)
                st.session_state[key] = res.data if res.ok else \
                    f"(Cortex error: {res.error})"
            st.write(st.session_state.get(key)
                     or eb.business_summary_fallback(t, a.lineage))

        df = pd.DataFrame([{
            "Target column": c.column, "Mapping type": c.mapping_type,
            "Source(s)": ", ".join(f"{x}.{y}" for x, y in c.ultimate_sources),
            "Business logic (QlikView)": c.qlik_expr,
            "Snowflake SQL": c.snowflake_sql,
            "Review": "; ".join(c.notes),
        } for c in cols])
        st.dataframe(df, hide_index=True, use_container_width=True)

    st.divider()
    st.subheader("Download full STTM")
    c1, c2 = st.columns(2)
    xlsx, yml = _sttm_bytes(a.name)
    c1.download_button("⬇ STTM.xlsx", xlsx, file_name="STTM.xlsx",
                       mime="application/vnd.openxmlformats-officedocument."
                            "spreadsheetml.sheet")
    c2.download_button("⬇ STTM.yaml", yml, file_name="STTM.yaml")


@st.cache_data(show_spinner=False)
def _sttm_bytes(a_key: str):  # cache keyed by analysis name
    a = st.session_state.analysis
    import tempfile
    from qv2dbt.generators import sttm
    d = tempfile.mkdtemp()
    xp, yp = os.path.join(d, "STTM.xlsx"), os.path.join(d, "STTM.yaml")
    sttm.generate(a.script, a.lineage, xp, yp)
    return open(xp, "rb").read(), open(yp, "rb").read()


# ---------------------------------------------------------------------------
# Page 5: Conversion
# ---------------------------------------------------------------------------
def page_conversion():
    st.header("5 · Conversion")
    a = _require()
    if not a:
        return
    st.write("Select target(s) and output type(s), then generate. "
             "Physical schema, dbt, view, procedure, or bare SELECT.")

    all_tables = [t.name for t in a.script.tables]
    csel1, csel2 = st.columns([1, 3])
    select_all = csel1.checkbox("Select all tables")
    default = all_tables if select_all else \
        [t.name for t in a.script.tables if t.layer == "mart"][:1]
    picked = csel2.multiselect("Tables", all_tables, default=default)

    st.write("**Output types**")
    oc = st.columns(5)
    targets = []
    if oc[0].checkbox("CREATE TABLE", True):
        targets.append("create_table")
    if oc[1].checkbox("dbt model", True):
        targets.append("dbt")
    if oc[2].checkbox("View"):
        targets.append("view")
    if oc[3].checkbox("SQL procedure"):
        targets.append("procedure")
    if oc[4].checkbox("SELECT"):
        targets.append("select")

    also_recon = st.checkbox("Include reconciliation query")
    ai_suggest = st.checkbox(
        "✨ AI-suggested SQL for flagged constructs (Cortex COMPLETE)",
        disabled=not sf.cortex_available(),
        help="For Peek/Aggr/set-analysis etc. Marked NEEDS REVIEW.")

    if not (picked and targets):
        st.info("Pick at least one table and one output type.")
        return

    conv = eb.converter(a)
    generated: list[tuple[str, str, str]] = []  # (label, lang, sql)
    for name in picked:
        t = a.script.table_by_name(name)
        out = conv.convert(t, targets)
        st.subheader(f"🎯 {name}")
        for typ in targets:
            label = {"create_table": "CREATE TABLE", "dbt": "dbt model",
                     "view": "View", "procedure": "SQL procedure",
                     "select": "SELECT"}[typ]
            with st.expander(f"{label} — {name}", expanded=(typ == "create_table")):
                st.code(out[typ], language="sql")
            generated.append((f"{name}·{label}",
                              "sql", out[typ]))
        if also_recon:
            rq = eb.reconciliation_sql(t, a.config)
            with st.expander(f"Reconciliation — {name}"):
                st.code(rq, language="sql")
            generated.append((f"{name}·recon", "sql", rq))
        if ai_suggest:
            with st.expander(f"✨ AI-suggested SQL (needs review) — {name}"):
                res = sf.cortex_complete(eb.ai_suggest_prompt(t, a.lineage),
                                         model=st.session_state.cortex_model)
                st.markdown(res.data if res.ok else f"(Cortex error: {res.error})")

    st.divider()
    combined = "\n\n".join(f"-- === {lbl} ===\n{sql}" for lbl, _l, sql in generated)
    d1, d2 = st.columns(2)
    d1.download_button("⬇ Download generated SQL", combined,
                       file_name="conversion.sql")
    run = d2.button("▶ Run in Snowflake", type="primary",
                    disabled=not sf.is_connected(),
                    help="Executes generated statements on the active session.")
    if run:
        stmts = [sql for _l, _lang, sql in generated]
        with st.spinner("Executing…"):
            results = sf.execute_script(stmts)
        for r in results:
            (st.success if r.ok else st.error)(
                f"{'OK' if r.ok else 'ERR'}: {r.data or r.error}")


# ---------------------------------------------------------------------------
# Page 6: Chatbot (Cortex Search / RAG)
# ---------------------------------------------------------------------------
def page_chat():
    st.header("6 · Chatbot — ask about the code")
    a = _require()
    if not a:
        return
    st.caption("Answers use Cortex Search if a service is configured, else "
               "Cortex COMPLETE over a local index of the parsed script.")

    with st.expander("⚙ Persist catalog & create Cortex Search service"):
        c = st.columns(5)
        db = c[0].text_input("Database", value=a.config["target"]["database"])
        sch = c[1].text_input("Schema", value="MIGRATION")
        tbl = c[2].text_input("Catalog table", value="QV_MIGRATION_CATALOG")
        svc_name = c[3].text_input("Search service", value="QV_MIGRATION_SEARCH")
        wh = c[4].text_input("Warehouse", value="COMPUTE_WH")
        setup_sql = eb.cortex_search_setup_sql(db, sch, tbl, svc_name, wh)
        b1, b2, b3 = st.columns(3)
        if b1.button("1 · Persist catalog", disabled=not sf.is_connected()):
            df = eb.catalog_dataframe(a)
            res = sf.save_dataframe(df, f"{db}.{sch}.{tbl}")
            (st.success if res.ok else st.error)(res.data or res.error)
        if b2.button("2 · Create search service",
                     disabled=not sf.is_connected()):
            results = sf.create_search_service(setup_sql)
            for r in results:
                (st.success if r.ok else st.error)(r.data or r.error)
            if all(r.ok for r in results):
                st.session_state["search_service"] = f"{db}.{sch}.{svc_name}"
        b3.download_button("⬇ setup SQL", setup_sql,
                           file_name="cortex_search_setup.sql")

    svc = st.text_input("Cortex Search service (DB.SCHEMA.SERVICE) — optional",
                        value=st.session_state.get("search_service", ""))
    corpus = eb.catalog_rows(a)

    for role, text in st.session_state.chat:
        with st.chat_message(role):
            st.markdown(text)

    q = st.chat_input("e.g. Which columns feed TotalRevenue? What does "
                      "FactTable contain?")
    if q:
        st.session_state.chat.append(("user", q))
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            if not sf.cortex_available():
                ans = _local_answer(q, corpus)
                st.markdown(ans)
                st.session_state.chat.append(("assistant", ans))
            elif svc:
                res = sf.cortex_search(svc, q, ["text", "id"], limit=6)
                if res.ok:
                    ctx = "\n\n".join(str(r) for r in res.data)
                    comp = sf.cortex_complete(
                        f"Answer using this context:\n{ctx}\n\nQ: {q}",
                        model=st.session_state.cortex_model)
                    ans = comp.data if comp.ok else res.error
                else:
                    ans = f"(Search error: {res.error})"
                st.markdown(ans)
                st.session_state.chat.append(("assistant", ans))
            else:
                res = sf.rag_answer(q, corpus,
                                    model=st.session_state.cortex_model)
                ans = (res.data["answer"] + f"\n\n_Sources: "
                       f"{', '.join(res.data['sources'])}_") if res.ok \
                    else f"(Cortex error: {res.error})"
                st.markdown(ans)
                st.session_state.chat.append(("assistant", ans))


def _local_answer(q: str, corpus: list[dict]) -> str:
    hits = sf._keyword_retrieve(q, corpus, 4)
    body = "\n\n".join(f"**{h['id']}**\n\n```\n{h['text'][:600]}\n```"
                       for h in hits)
    return ("_(Not connected to Snowflake — showing the most relevant parsed "
            f"records; connect for a Cortex-written answer.)_\n\n{body}")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _require():
    a = st.session_state.analysis
    if not a:
        st.info("Upload and parse a script on page 1 first.")
    return a


def _list_df(items, label):
    st.dataframe(pd.DataFrame({label: items}) if items else
                 pd.DataFrame(columns=[label]),
                 hide_index=True, use_container_width=True)


def main():
    _ss()
    page = sidebar()
    {
        "1 · Upload & Parse": page_upload,
        "2 · Inventory": page_inventory,
        "3 · Lineage": page_lineage,
        "4 · STTM": page_sttm,
        "5 · Conversion": page_conversion,
        "6 · Chatbot": page_chat,
    }[page]()


if __name__ == "__main__":
    main()
