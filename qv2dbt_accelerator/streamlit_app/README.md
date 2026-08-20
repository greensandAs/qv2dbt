# qv2dbt Studio — Streamlit app

A UI over the qv2dbt accelerator: upload a QlikView app or script, explore the
inventory and lineage, review the STTM with AI-written business descriptions,
generate conversions (CREATE TABLE / dbt / view / procedure), and ask a Cortex
chatbot about the code.

## Pages
1. **Upload & Parse** — upload `.qvf/.qvw/.qvs/.txt`; parses in place and lists the script's pages (tabs); downloads the full artifact bundle (ZIP).
2. **Inventory** — source/target/staging/intermediate/mapping tables, referred QVDs, input files, output files/QVDs, variables, dependencies, and an effort/complexity score per table.
3. **Lineage** — multi-select filter by target table(s) and/or source table/file; column-level mapping table + a graph.
4. **STTM** — per-target column mapping with business logic; **Cortex-generated business functionality** per target; download `STTM.xlsx` / `STTM.yaml`.
5. **Conversion** — pick tables (with *select all*) and output types (CREATE TABLE, dbt, view, SQL procedure, SELECT) via checkboxes; view/download generated SQL; optional **Run in Snowflake**; optional reconciliation queries.
6. **Chatbot** — ask about the code. Uses a **Cortex Search** service if you provide one, otherwise Cortex `COMPLETE` over a local index of the parsed script (RAG-lite). Falls back to keyword retrieval when disconnected. Includes a **catalog persistence + Cortex Search setup** panel (below).

## Durable catalog + Cortex Search
The Chatbot page can **persist the mapping catalog** (one row per target column
+ control block, with a searchable `TEXT` field) to a Snowflake table, then
**create a Cortex Search service** over it with one click — after which the
chatbot answers from that service. A downloadable `cortex_search_setup.sql` is
also provided. This gives the chatbot a durable, queryable corpus instead of an
in-session index.

## AI-suggested conversions
On the **Conversion** page, tick *AI-suggested SQL* to have Cortex `COMPLETE`
propose Snowflake SQL for flagged / hard-to-convert constructs (Peek, Aggr, set
analysis, control flow), each marked **NEEDS REVIEW** — the deterministic engine
stays deterministic; AI only assists the flagged remainder.

## Snowflake & Cortex
Session is **auto-detected**:
- Inside **Streamlit-in-Snowflake**, the native Snowpark session and Cortex are used automatically — no setup.
- **Standalone**, connect from the sidebar, or provide `.streamlit/secrets.toml`:
  ```toml
  [snowflake]
  account = "..."
  user = "..."
  password = "..."
  role = "..."
  warehouse = "..."
  database = "..."
  ```
  (or `SNOWFLAKE_*` environment variables.)

Cortex features (chatbot, AI-suggested conversions for flagged constructs,
business-functionality text, reconciliation/effort assistance) activate when
connected; otherwise the app runs fully for parsing, inventory, lineage, STTM,
and code generation.

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

To deploy in **Streamlit-in-Snowflake**, upload `app.py`, `engine_bridge.py`,
`snowflake_utils.py` and the `qv2dbt` package (from `../src`) to a stage/app
and set the main file to `app.py`.

## Optional: Cortex Search service
For the best chatbot, persist the catalog (see `engine_bridge.catalog_rows`)
to a table and create a Cortex Search service over its `text` column, then
enter `DB.SCHEMA.SERVICE` on the Chatbot page.
