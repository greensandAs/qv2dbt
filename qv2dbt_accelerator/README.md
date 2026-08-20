# qv2dbt — QlikView → Snowflake Migration Accelerator

> **Tiger Analytics** | Accelerate QlikView to Snowflake migrations with automated parsing, translation, lineage tracking, and a production-grade Streamlit UI.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Pipeline Stages](#pipeline-stages)
4. [Streamlit App — Page-by-Page Guide](#streamlit-app--page-by-page-guide)
5. [Installation: Snowflake (Streamlit in Snowflake)](#installation-snowflake-streamlit-in-snowflake)
6. [Installation: Local Hosted Streamlit](#installation-local-hosted-streamlit)
7. [CLI Usage (Headless)](#cli-usage-headless)
8. [Configuration](#configuration)
9. [What Gets Converted](#what-gets-converted)
10. [Limitations](#limitations)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        qv2dbt Accelerator Architecture                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  INPUT                     PIPELINE                        OUTPUT            │
│  ─────                     ────────                        ──────            │
│                                                                             │
│  .qvs / .qvf / .qvw  ─┐                                                    │
│                         │   ┌──────────────┐                                │
│                         ├──►│ 1. Preprocess │  Strip comments, expand vars   │
│                         │   └──────┬───────┘                                │
│                         │          ▼                                         │
│                         │   ┌──────────────┐                                │
│                         └──►│ 2. Parse     │  Build IR (tables/fields/joins) │
│                             └──────┬───────┘                                │
│                                    ▼                                         │
│                             ┌──────────────┐                                │
│                             │ 3. Translate │  QlikView expr → Snowflake SQL  │
│                             └──────┬───────┘                                │
│                                    ▼                                         │
│                             ┌──────────────┐                                │
│                             │ 4. Transform │  Assign layers, resolve refs    │
│                             └──────┬───────┘                                │
│                                    ▼                                         │
│                             ┌──────────────┐   ┌───────────────────────┐    │
│                             │ 5. Generate  │──►│ Snowflake RAW DDL     │    │
│                             │              │──►│ dbt project (full)    │    │
│                             │              │──►│ SQL Views / SELECTs   │    │
│                             │              │──►│ Stored Procedures     │    │
│                             │              │──►│ STTM (Excel + YAML)   │    │
│                             │              │──►│ Lineage (JSON/HTML)   │    │
│                             │              │──►│ Migration Report      │    │
│                             └──────────────┘   └───────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                  Streamlit UI (qv2dbt Studio)                        │    │
│  │  Upload → Inventory → Lineage → STTM → Conversion → Chatbot        │    │
│  │  + Run in Snowflake │ Export ZIP │ Cortex AI │ Persist to Stage      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
qv2dbt_accelerator/
├── README.md                          ← This file
├── requirements.txt                   ← Python deps (PyYAML, openpyxl)
├── pyproject.toml                     ← Package metadata
│
├── src/qv2dbt/                        ← Core engine (Python package)
│   ├── __init__.py
│   ├── __main__.py                    ← CLI entry point
│   ├── cli.py                         ← Argument parsing
│   ├── config.py                      ← YAML config loader
│   ├── preprocessor.py                ← Stage 1: strip comments, expand $(vars)
│   ├── parser.py                      ← Stage 2: LOAD/JOIN/MAPPING → IR
│   ├── expressions.py                 ← Stage 3: QlikView → Snowflake functions
│   ├── transformer.py                 ← Stage 4: layer assignment, ref resolution
│   ├── models.py                      ← IR dataclasses (QvTable, QvField, etc.)
│   ├── lineage.py                     ← Column-level lineage builder
│   ├── pipeline.py                    ← End-to-end orchestrator
│   ├── qvf_extractor.py              ← Binary .qvf/.qvw → text extraction
│   ├── utils.py                       ← Naming, type guessing helpers
│   ├── control.py                     ← SUB/FOR/IF block capture
│   └── generators/                    ← Stage 5: Output generators
│       ├── snowflake_ddl.py           ← CREATE TABLE DDL
│       ├── dbt_models.py              ← dbt SQL models
│       ├── dbt_scaffold.py            ← dbt_project.yml, sources, schema
│       ├── sql_views.py               ← CREATE VIEW (non-dbt path)
│       ├── sttm.py                    ← STTM Excel + YAML
│       ├── lineage_out.py             ← Lineage JSON/Mermaid/HTML
│       ├── report.py                  ← Migration report (MD + JSON)
│       └── control_stubs.py           ← Manual conversion stubs
│
├── config/
│   └── default_config.yml             ← Function mappings, naming, target DB
│
├── streamlit_app/                     ← Production Streamlit UI
│   ├── snowflake.yml                  ← Snowflake Workspace config
│   ├── pyproject.toml                 ← App dependencies
│   ├── streamlit_app.py               ← Main orchestrator (thin)
│   ├── engine_bridge.py               ← Full accelerator wrapper
│   ├── snowflake_utils.py             ← Cortex AI + stage persistence
│   ├── .streamlit/config.toml         ← Tiger Analytics theme
│   ├── config/
│   │   ├── __init__.py
│   │   └── brand.py                   ← Color tokens, theme detection
│   ├── components/
│   │   ├── __init__.py
│   │   ├── header.py                  ← Header + footer rendering
│   │   ├── sidebar.py                 ← Navigation + model picker
│   │   └── styles.py                  ← CSS injection
│   └── pages/
│       ├── __init__.py
│       ├── upload.py                  ← Page 1: Upload & Parse
│       ├── inventory.py               ← Page 2: Inventory + Effort Scoring
│       ├── lineage.py                 ← Page 3: Column-level Lineage
│       ├── sttm.py                    ← Page 4: Source-to-Target Mapping
│       ├── conversion.py              ← Page 5: DDL/View/dbt + Run in SF
│       └── chatbot.py                 ← Page 6: Cortex AI Assistant
│
├── samples/                           ← Example QVS scripts
│   ├── sales_pipeline.qvs
│   ├── executive_dashboard.qvs
│   └── stress_test.qvs
│
├── examples/                          ← Pre-generated output examples
│   ├── demo/
│   ├── exec_full/
│   └── sample_full/
│
└── tests/                             ← pytest test suite
    ├── conftest.py
    ├── test_parser.py
    ├── test_expressions.py
    ├── test_preprocessor.py
    ├── test_end_to_end.py
    ├── test_sttm_lineage.py
    └── test_control_sqlviews.py
```

---

## Pipeline Stages

### Stage 1 — Preprocessor (`preprocessor.py`)

- Strips block comments (`/* ... */`) and line comments (`//`)
- Respects quoted strings and bracket identifiers
- Captures `SET` / `LET` variables into a symbol table
- Expands `$(variable)` references inline
- Splits the script into individual statements

### Stage 2 — Parser (`parser.py`)

- Classifies statements: `LOAD`, `JOIN`, `MAPPING LOAD`, `RESIDENT`, `DROP`, `STORE`, `CONCATENATE`, `RENAME`, control flow
- Builds the **Intermediate Representation (IR)**: `QvScript` → `QvTable[]` → `QvField[]` + `QvJoin[]`
- Handles: `WHERE`, `GROUP BY`, `DISTINCT`, `ORDER BY`, `NOCONCATENATE`
- Captures control blocks (`SUB`, `FOR`, `IF`, `DO`, `SWITCH`) for manual review

### Stage 3 — Expression Translator (`expressions.py`)

- Recursively translates QlikView functions → Snowflake SQL
- 80+ function mappings: `if()` → `CASE WHEN`, `Num()` → `TO_NUMBER()`, `Date()` → `TO_DATE()`, `ApplyMap()` → LEFT JOIN, etc.
- Handles nested expressions, string concatenation (`&` → `||`), operators
- Flags untranslatable constructs (e.g. `Peek`, `Previous`, `Aggr`, `set analysis`)

### Stage 4 — Transformer (`transformer.py`)

- Assigns dbt **layers** (staging / intermediate / mart) based on config patterns
- Resolves `RESIDENT` references into model dependencies
- Infers implicit join keys (QlikView auto-joins on same-named columns)
- Finalises `WHERE` and `GROUP BY` translation

### Stage 5 — Generators (`generators/`)

| Generator | Output | Purpose |
|-----------|--------|---------|
| `snowflake_ddl.py` | `CREATE TABLE` DDL | Physical RAW landing schema |
| `dbt_models.py` | `.sql` models per table | dbt project models |
| `dbt_scaffold.py` | `dbt_project.yml`, `sources.yml`, `schema.yml`, `packages.yml` | Full runnable dbt project |
| `sql_views.py` | `CREATE OR REPLACE VIEW` | Non-dbt Snowflake path |
| `sttm.py` | `STTM.xlsx` + `STTM.yaml` | Column-level source-to-target mapping |
| `lineage_out.py` | `lineage.json`, `.mmd`, `.md`, `lineage_explorer.html` | Interactive lineage explorer |
| `report.py` | `migration_report.md` + `.json` | Scoping deliverable |
| `control_stubs.py` | `manual_conversion_stubs.md` | Guidance for control flow |

---

## Streamlit App — Page-by-Page Guide

### Page 1: Upload & Parse

**Script:** `pages/upload.py`

| Feature | Detail |
|---------|--------|
| Multi-file upload | `.qvs`, `.qvf`, `.qvw`, `.txt` (up to 50 MB each) |
| Binary extraction | `.qvf`/`.qvw` auto-decompressed via `qvf_extractor.py` |
| Encoding detection | UTF-8, UTF-8-BOM, Latin-1 auto-detected |
| Progress bar | Per-file progress with toast notifications |
| Validation | Size limits, extension checks, empty-file rejection |
| Output | Table count, source/target split, auto-translatable %, script tabs |

**Process:** `engine_bridge.analyze()` → `parse_script()` → `Transformer().run()` → `build_lineage()`

---

### Page 2: Inventory

**Script:** `pages/inventory.py`

| Feature | Detail |
|---------|--------|
| Layer distribution | Staging / Intermediate / Mart / Mapping counts |
| Table details | Name, layer, load kind, source, field count, join count, review items |
| Effort scoring | Points-based complexity: Low / Medium / High per table |
| Control flow | SUB/FOR/IF blocks flagged for manual review |
| Variables | All SET/LET variables with values |

**Process:** `engine_bridge.inventory()` + `engine_bridge.effort_scores()`

---

### Page 3: Lineage

**Script:** `pages/lineage.py`

| Feature | Detail |
|---------|--------|
| Column-level trace | Source → intermediate → target mapping |
| Filters | By table, by layer, review-only toggle |
| Ultimate sources | Traces through RESIDENT refs to original QVD/file/SQL source |
| Mapping types | direct, derived, aggregate, lookup, constant, join |
| CSV export | Download filtered lineage as CSV |

**Process:** `engine_bridge.lineage_rows()` → `lineage.for_table()` per target

---

### Page 4: STTM (Source-to-Target Mapping)

**Script:** `pages/sttm.py`

| Feature | Detail |
|---------|--------|
| Per-target view | Field mapping grouped by target table |
| Expression comparison | QlikView expression ↔ Snowflake SQL side-by-side |
| Review flags | Items needing manual review highlighted |
| Full download | CSV export of complete STTM |

**Process:** Same lineage data reshaped per target for STTM deliverable format

---

### Page 5: Conversion

**Script:** `pages/conversion.py`

| Feature | Detail |
|---------|--------|
| Output types | CREATE TABLE DDL, CREATE VIEW, dbt model, Stored Procedure, SELECT |
| Table selector | Multi-select which tables to convert |
| Run in Snowflake | Execute DDL/views/procedures directly via `session.sql()` |
| ZIP export | Full pipeline output (dbt project + DDL + STTM.xlsx + lineage HTML) |
| SQL download | Combined SQL file download |

**Process:** `engine_bridge.Converter()` wraps `DbtModelGenerator` + `SqlViewGenerator` + DDL generation

---

### Page 6: Chatbot

**Script:** `pages/chatbot.py`

| Feature | Detail |
|---------|--------|
| Cortex AI | Powered by Snowflake Cortex (`COMPLETE()`) |
| Context-aware | Full script + lineage + table details injected as prompt context |
| Quick actions | "Summarise scope", "List review items", "Suggest SQL for flagged" |
| Model picker | mistral-large2, llama3.1-70b, snowflake-arctic, mixtral-8x7b |

**Process:** `snowflake_utils.cortex_chat()` → `SNOWFLAKE.CORTEX.COMPLETE(model, prompt)`

---

## Installation: Snowflake (Streamlit in Snowflake)

### Prerequisites

- Snowflake account with **Streamlit in Snowflake** enabled
- A **compute pool** (e.g. `SYSTEM_COMPUTE_POOL_CPU`)
- A **warehouse** (e.g. `COMPUTE_WH`)
- Role with `CREATE STREAMLIT` privilege

### Steps

1. **Upload the entire `qv2dbt_accelerator/` folder** to a Snowflake Workspace:
   - Go to **Projects → Workspaces** in Snowsight
   - Create or open a workspace
   - Upload/sync the `qv2dbt_accelerator/` directory

2. **Navigate to `streamlit_app/`** in the workspace file tree

3. **Verify `snowflake.yml`** — update warehouse/pool if different:
   ```yaml
   query_warehouse: COMPUTE_WH        # ← your warehouse
   compute_pool: SYSTEM_COMPUTE_POOL_CPU  # ← your compute pool
   ```

4. **Click Run** in the Snowsight Workspace toolbar

5. The app opens with the Tiger Analytics branded UI. Upload a `.qvs` to begin.

### Notes for SiS

- **No pip install needed** — `pyproject.toml` declares `streamlit[snowflake]>=1.54.0` which is pre-installed
- **No secrets file needed** — `st.connection("snowflake")` uses the embedded session
- The `src/qv2dbt/` engine is loaded at runtime via `sys.path` from the workspace filesystem
- **Cortex AI** requires the model to be available in your region (`SHOW CORTEX SEARCH SERVICES` or check docs)

---

## Installation: Local Hosted Streamlit

### Prerequisites

- Python 3.11+
- A Snowflake account (for Cortex AI features; the parser works offline)

### Steps

1. **Clone / download** the `qv2dbt_accelerator/` folder:
   ```bash
   cd qv2dbt_accelerator
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install streamlit snowflake-snowpark-python openpyxl
   ```

3. **Configure Snowflake connection** (for Cortex + Run in Snowflake features):
   ```bash
   mkdir -p streamlit_app/.streamlit
   ```

   Create `streamlit_app/.streamlit/secrets.toml`:
   ```toml
   [connections.snowflake]
   account = "your_account"
   user = "your_user"
   password = "your_password"
   warehouse = "COMPUTE_WH"
   database = "YOUR_DB"
   schema = "YOUR_SCHEMA"
   role = "YOUR_ROLE"
   ```

4. **Run the app**:
   ```bash
   cd streamlit_app
   streamlit run streamlit_app.py --server.port 8501
   ```

5. Open `http://localhost:8501` in your browser.

### Running without Snowflake (offline mode)

The parser, lineage, and conversion work fully offline. Only these features need Snowflake:
- "Run in Snowflake" button (executes SQL)
- Cortex AI chatbot
- Save/Load persistence (uses Snowflake stage)

To run offline, the app will show a connection error on startup — you can ignore it and use the `engine_bridge` module directly:

```python
import sys
sys.path.insert(0, "src")
from engine_bridge import analyze

with open("your_script.qvs", "rb") as f:
    analysis = analyze(f.read(), "your_script.qvs")

# analysis.script.tables → parsed tables
# analysis.lineage → column-level lineage
```

---

## CLI Usage (Headless)

Run the full pipeline without the UI:

```bash
python -m qv2dbt samples/sales_pipeline.qvs -o ./output

# Binary Qlik apps:
python -m qv2dbt "Executive Dashboard.qvf" -o ./output

# With config overrides:
python -m qv2dbt script.qvs -o ./output -c my_overrides.yml
```

Output:
```
output/
├── snowflake_raw_ddl.sql
├── migration_report.md / .json
├── manual_conversion_stubs.md
├── sql_views/
│   ├── all_views.sql
│   ├── views/<TABLE>.sql
│   └── selects/<TABLE>.sql
├── sttm_and_lineage/
│   ├── STTM.xlsx
│   ├── STTM.yaml
│   ├── lineage.json / .mmd / .md
│   └── lineage_explorer.html
└── dbt_project/
    ├── dbt_project.yml
    ├── models/{staging,intermediate,marts}/
    ├── macros/apply_map.sql
    └── ...
```

---

## Configuration

Copy any subset of `config/default_config.yml` into an overrides file:

```yaml
target:
  database: MY_DW
  staging_schema: RAW
  mart_schema: ANALYTICS
  identifier_case: upper

naming:
  staging_prefix: stg_
  intermediate_prefix: int_
  mart_prefix: mart_

layers:
  mart_name_patterns:
    - "*_fact"
    - "*_dim"
    - "*_summary"
```

---

## What Gets Converted

| QlikView Construct | Snowflake Target |
|-------------------|------------------|
| `LOAD ... FROM x.qvd/.csv` | Staging model + `source()` + RAW DDL |
| `LOAD ... RESIDENT` | Intermediate model + `ref()` |
| `LEFT/INNER/OUTER JOIN` | SQL `JOIN ... USING (keys)` |
| `CONCATENATE` | `UNION ALL` |
| `MAPPING LOAD` + `ApplyMap()` | Mapping model + `apply_map()` macro |
| `if(cond, then, else)` | `CASE WHEN ... THEN ... ELSE ... END` |
| `Date() / Num() / Left() / Len()` | `TO_DATE / TO_NUMBER / LEFT / LENGTH` |
| `& (concat)` | `\|\|` |
| `WHERE` | `WHERE` (translated expressions) |
| `GROUP BY` | `GROUP BY` + aggregate warnings |
| `STORE` | Recorded in report |
| `DROP TABLE` | Handled by dbt materialization |
| `SUB / FOR / IF / DO` | Captured in manual_conversion_stubs.md |

---

## Limitations

| Construct | Status |
|-----------|--------|
| `INLINE` tables | Captured, not fully translated |
| `Peek()` / `Previous()` | Flagged — suggest `LAG()` / `LEAD()` |
| `Aggr()` | Flagged — suggest window functions |
| `AutoNumber` | Flagged — suggest `ROW_NUMBER()` |
| `$(variable)` dynamic LOAD/SQL | Flagged for manual review |
| Section Access | Not processed |
| Binary apps (encrypted) | Error with extraction guidance |

---

## License

Internal — Tiger Analytics. Not for distribution.
