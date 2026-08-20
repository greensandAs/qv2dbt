# qv2dbt — QlikView → dbt / Snowflake Migration Accelerator

A configurable Python framework that reads a QlikView load script (`.qvs`) and
generates, in one pass:

1. **Snowflake RAW landing DDL** — a `CREATE TABLE` per external QVD / file / SQL source.
2. **dbt models** — one model per QlikView table, organised into `staging` → `intermediate` → `marts`, with QlikView expressions translated to Snowflake SQL.
3. **A complete dbt project scaffold** — `dbt_project.yml`, `sources.yml`, per-layer `schema.yml`, a `profiles.yml` template, `packages.yml`, and an `apply_map()` macro that resolves QlikView `ApplyMap()`.
4. **A migration & lineage report** (Markdown + JSON) — object inventory, field-level lineage, an auto-translatable %, and an explicit list of everything needing manual review.

## Why it exists

Hand-migrating QlikView ETL is slow and error-prone. This accelerator does the
mechanical 80–95% deterministically and, crucially, **flags what it cannot
prove** rather than guessing silently — so an engineer reviews a short list
instead of re-reading the whole script.

## Install & run

```bash
pip install -r requirements.txt          # PyYAML (+ pytest for the test suite)

python -m qv2dbt path/to/script.qvs -o ./output
# optional: -c my_overrides.yml to retune mappings/naming per engagement
```

Output layout:

```
output/
├── snowflake_raw_ddl.sql        # run this in Snowflake first
├── migration_report.md / .json  # scoping & lineage deliverable
└── dbt_project/                 # runnable dbt project (dbt deps && dbt build)
    ├── models/{staging,intermediate,marts}/
    ├── macros/apply_map.sql
    └── ...
```

## Streamlit app (qv2dbt Studio)

A full UI lives in `streamlit_app/` (`streamlit run app.py`). Six pages: Upload &
Parse, Inventory, Lineage (multi-select filter), STTM (with Cortex-written
business descriptions), Conversion (CREATE TABLE / dbt / view / procedure with
select-all + optional *Run in Snowflake*), and a Cortex chatbot. Snowflake
session is auto-detected (Streamlit-in-Snowflake or standalone via secrets);
all Cortex features degrade gracefully when disconnected. See
`streamlit_app/README.md`.

## Binary Qlik apps (.qvf / .qvw)

Point the tool at a binary Qlik app and it extracts the embedded load script
automatically (decompresses the internal stream, keeps the canonical copy),
then runs the full pipeline:

```bash
python -m qv2dbt "Executive Dashboard.qvf" -o ./output
```

The extracted script is written to `<name>_extracted.qvs` in the output folder
for review. If the script can't be located (encrypted / section-access), the
tool tells you to export the `.qvs` from Qlik and run on that.

## Source-to-Target Mapping (STTM) + Lineage

Every run also produces, under `output/sttm_and_lineage/`:

| File | What it is |
|---|---|
| `STTM.xlsx` | Target Inventory, Source Inventory, and a column-level **STTM** (target col, mapping type, source table/column, QlikView business logic, Snowflake SQL, review notes) |
| `STTM.yaml` | The same mapping, machine-readable for codegen/diffing |
| `lineage.json` | Column-level lineage graph (nodes + edges + ultimate sources) |
| `lineage.mmd` / `lineage.md` | Mermaid table-level graph + per-target column lineage (for dbt docs) |
| `lineage_explorer.html` | Self-contained **interactive explorer** — pick any target column, trace it back through every layer to source columns |

Each column is classified as `direct`, `derived`, `aggregate`, `lookup`,
`constant`, or `join`. Column references are traced through `RESIDENT` refs and
`JOIN`s to the ultimate external source table/column, so the STTM shows true
end-to-end mapping — this is what drives building the dbt/SQL views for each
target. Which tables count as **targets** is controlled by
`layers.mart_name_patterns` in the config.

## Plain SQL views / SELECTs per target (non-dbt path)

Alongside the dbt project, every run emits fully-resolved Snowflake SQL under
`output/sql_views/`:

  * `all_views.sql` - every target as `CREATE OR REPLACE VIEW`, in dependency order
  * `views/<name>.sql` - one CREATE VIEW per target
  * `selects/<name>.sql` - the bare SELECT per target

These use physical `database.schema.object` references (no Jinja) and inline
the `ApplyMap` lookups as correlated subqueries, so they run directly in
Snowflake or any orchestrator - useful when a target needs a plain view/SELECT
rather than a dbt model.

## Control flow (SUB / FOR / IF / DO / SWITCH)

QlikView control flow has no row-level SQL equivalent, so it is **captured, not
guessed**. Each block is recorded with conversion guidance in
`output/manual_conversion_stubs.md` (and summarised in the migration report).
Inner `LOAD`s are still parsed into models; only the control scaffolding needs
manual work. Variables that build code dynamically (`$()` expansion / embedded
LOAD/SQL) are flagged too.

## How it works (pipeline)

| Stage | Module | Responsibility |
|---|---|---|
| 1. Preprocess | `preprocessor.py` | strip comments (quote/bracket-aware), capture `SET`/`LET`, expand `$(var)`, split statements |
| 2. Parse | `parser.py` | classify `LOAD`/`JOIN`/`MAPPING`/`RESIDENT`/`DROP`/`STORE`, build the IR (`models.py`) |
| 3. Translate | `expressions.py` | QlikView functions/operators → Snowflake SQL; flag unknowns |
| 4. Transform | `transformer.py` | translate every field/WHERE, finalise dbt layers |
| 5. Generate | `generators/` | Snowflake DDL, dbt models, project scaffold, report |

## What is converted automatically

| QlikView | Target |
|---|---|
| `LOAD ... FROM x.qvd/.csv` | staging model + `source()` + RAW DDL |
| `LOAD ... RESIDENT` | intermediate model + `ref()` |
| `LEFT/INNER/OUTER JOIN` | SQL `JOIN ... USING (inferred common cols)` |
| `CONCATENATE` | `UNION ALL` |
| `MAPPING LOAD` + `ApplyMap()` | mapping model + `apply_map()` macro |
| `if / Date / Num / Left / Len / &` … | `CASE / TO_DATE / TO_NUMBER / LEFT / LENGTH / \|\|` … |
| `DROP / STORE / RENAME / control flow` | recorded in the report (handled by dbt materialization) |

Everything is driven by `config/default_config.yml` — function mappings, naming
prefixes, target database/schemas, and mart-detection patterns — so the tool is
retuned per client without code changes.

## Configuration

Copy any subset of `config/default_config.yml` into an overrides file and pass
`-c`. Common tweaks: `target.database`/schemas, `naming.*` prefixes,
`layers.mart_name_patterns`, and adding entries under `functions:` for
project-specific QlikView functions.

## Tests

```bash
pytest            # preprocessor, expression translator, parser, end-to-end
```

The `samples/sales_pipeline.qvs` script exercises every supported construct and
is used by the end-to-end test.

## Limitations (v0.1)

QlikView `INLINE` tables, `Peek/Previous`, `Aggr()`, `AutoNumber`, and control
flow (`SUB`/`FOR`/`IF`) are recorded for manual handling rather than translated.
Join keys are inferred from identically-named columns (QlikView's own rule);
where none are found the model emits a `TODO` for the engineer to specify keys.
